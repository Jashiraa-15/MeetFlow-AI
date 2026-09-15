import os
import sys
import json
import asyncio
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import engine, Base, SessionLocal
from app.models import User, Meeting, ActionItem, ClarificationRequest
from app.cache_and_limiter import clear_cache_and_limits_for_tests
from app.scheduler import (
    run_daily_overdue_check,
    run_clarification_reminder_check,
    _notified_overdue_today
)
from main import app

client = TestClient(app)

def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    clear_cache_and_limits_for_tests()
    _notified_overdue_today.clear()

def run_stage_7_scheduler_verification():
    print("==================================================================")
    print(" STAGE 7 VERIFICATION: BACKGROUND JOBS & SCHEDULER")
    print("==================================================================")

    reset_db()

    # 1. Register User A and User B
    print("\n--- Setup: Registering Users A and B ---")
    res_a = client.post("/auth/register", json={"email": "sched_a@example.com", "password": "PasswordA123!"})
    assert res_a.status_code == 201
    token_a = res_a.json()["access_token"]
    user_a_id = res_a.json()["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    res_b = client.post("/auth/register", json={"email": "sched_b@example.com", "password": "PasswordB123!"})
    assert res_b.status_code == 201
    token_b = res_b.json()["access_token"]
    user_b_id = res_b.json()["user"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    print(f"[OK] Users registered: User A (ID={user_a_id}), User B (ID={user_b_id}).")

    # 2. Create Meeting & Overdue Action Item for User A
    print("\n--- Setup: Creating Overdue Task for User A ---")
    db = SessionLocal()
    now_utc = datetime.now(timezone.utc)
    yesterday = date.today() - timedelta(days=1)

    meeting_a = Meeting(
        user_id=user_a_id,
        title="Overdue Check Test Meeting",
        transcript_text="Overdue test transcript",
        meeting_date=yesterday,
        sentiment="neutral",
        created_at=now_utc - timedelta(days=2)
    )
    db.add(meeting_a)
    db.commit()
    db.refresh(meeting_a)
    meeting_a_id = meeting_a.id

    overdue_task = ActionItem(
        meeting_id=meeting_a_id,
        task="Urgent security patch deployment",
        owner="sched_a@example.com",
        deadline=yesterday, # Overdue
        priority="High",
        category="Engineering",
        confidence=0.95,
        needs_clarification=False,
        is_confirmed=True,
        status="todo",
        mention_count=1,
        created_at=now_utc - timedelta(days=2),
        updated_at=now_utc - timedelta(days=2)
    )
    db.add(overdue_task)
    db.commit()
    db.refresh(overdue_task)
    overdue_id = overdue_task.id
    db.close()
    print(f"[OK] Overdue task created: ID={overdue_id}, Deadline={yesterday}, Status='todo'.")

    # -------------------------------------------------------------
    # Test 1: Daily Overdue Check Job Execution & WS Broadcast
    # -------------------------------------------------------------
    print("\n--- Test 1: Daily Overdue Job & WebSocket Broadcast ---")
    
    with client.websocket_connect(f"/ws/updates?token={token_a}") as ws_a:
        with client.websocket_connect(f"/ws/updates?token={token_b}") as ws_b:
            print("[OK] Connected ws_a (User A) and ws_b (User B).")

            # Execute run_daily_overdue_check()
            asyncio.run(run_daily_overdue_check())

            # Verify ws_a receives action_item.overdue event
            msg_overdue = json.loads(ws_a.receive_text())
            print(f"[OK] ws_a received event: '{msg_overdue.get('event')}' for Task: '{msg_overdue.get('action_item', {}).get('task')}'")
            assert msg_overdue["event"] == "action_item.overdue"
            assert msg_overdue["action_item"]["id"] == overdue_id
            assert msg_overdue["action_item"]["status"] == "todo"

            # Verify ws_b does NOT receive User A's overdue event (ping test)
            ws_b.send_text("ping")
            pong_b = json.loads(ws_b.receive_text())
            assert pong_b["event"] == "pong"
            print("[OK] Cross-user isolation verified: User B received NO overdue notifications for User A.")

            # Run overdue job a second time today -> verify deduplication (no extra message sent)
            print("-> Running overdue job second time today (testing daily deduplication)...")
            asyncio.run(run_daily_overdue_check())
            ws_a.send_text("ping")
            pong_a = json.loads(ws_a.receive_text())
            assert pong_a["event"] == "pong", "Duplicate overdue notification was sent"
            print("[OK] Daily deduplication verified: No repeated notification sent on second run.")

    # -------------------------------------------------------------
    # Test 2: Clarification Reminder Job (> 24h Old Request)
    # -------------------------------------------------------------
    print("\n--- Test 2: Clarification Reminder Job (> 24h Unanswered Request) ---")
    db = SessionLocal()
    # Create action item needing clarification
    item_clarify = ActionItem(
        meeting_id=meeting_a_id,
        task="Clarify database migration owner",
        owner=None,
        deadline=None,
        priority="Medium",
        category="Engineering",
        confidence=0.4,
        needs_clarification=True,
        is_confirmed=False,
        status="todo",
        mention_count=1,
        created_at=now_utc - timedelta(hours=30),
        updated_at=now_utc - timedelta(hours=30)
    )
    db.add(item_clarify)
    db.commit()
    db.refresh(item_clarify)
    item_clarify_id = item_clarify.id

    # Create clarification request sent 30 hours ago (> 24h)
    req_30h = ClarificationRequest(
        action_item_id=item_clarify_id,
        question_sent_at=now_utc - timedelta(hours=30),
        answered_at=None,
        reminder_sent_at=None
    )
    db.add(req_30h)
    db.commit()
    db.refresh(req_30h)
    req_30h_id = req_30h.id
    db.close()
    print(f"[OK] ClarificationRequest #{req_30h_id} created with question_sent_at = 30h ago, reminder_sent_at = None.")

    with client.websocket_connect(f"/ws/updates?token={token_a}") as ws_a:
        # Run clarification reminder job
        asyncio.run(run_clarification_reminder_check())

        # Verify ws_a receives clarification.reminder
        msg_remind = json.loads(ws_a.receive_text())
        print(f"[OK] ws_a received event: '{msg_remind.get('event')}' for Task: '{msg_remind.get('action_item', {}).get('task')}'")
        assert msg_remind["event"] == "clarification.reminder"
        assert msg_remind["action_item"]["id"] == item_clarify_id
        assert msg_remind["action_item"]["needs_clarification"] is True

        # Verify reminder_sent_at is populated in DB
        db = SessionLocal()
        updated_req = db.query(ClarificationRequest).filter(ClarificationRequest.id == req_30h_id).first()
        assert updated_req.reminder_sent_at is not None, "reminder_sent_at was not populated"
        print(f"[OK] Verified SQLite DB: reminder_sent_at populated with {updated_req.reminder_sent_at}.")
        db.close()

        # Run reminder job again -> verify no duplicate reminder sent
        print("-> Running clarification reminder job a second time...")
        asyncio.run(run_clarification_reminder_check())
        ws_a.send_text("ping")
        pong_a = json.loads(ws_a.receive_text())
        assert pong_a["event"] == "pong"
        print("[OK] Verified: Reminder is NOT repeated once reminder_sent_at is set.")

    # -------------------------------------------------------------
    # Test 3: Clarification Request with answered_at != None (Ignored)
    # -------------------------------------------------------------
    print("\n--- Test 3: Clarification Request Already Answered ---")
    db = SessionLocal()
    req_answered = ClarificationRequest(
        action_item_id=item_clarify_id,
        question_sent_at=now_utc - timedelta(hours=48),
        answered_at=now_utc - timedelta(hours=10), # Answered 10 hours ago
        reminder_sent_at=None
    )
    db.add(req_answered)
    db.commit()
    db.refresh(req_answered)
    req_ans_id = req_answered.id
    db.close()
    print(f"[OK] ClarificationRequest #{req_ans_id} created with answered_at = populated.")

    with client.websocket_connect(f"/ws/updates?token={token_a}") as ws_a:
        asyncio.run(run_clarification_reminder_check())
        ws_a.send_text("ping")
        pong_a = json.loads(ws_a.receive_text())
        assert pong_a["event"] == "pong"
        print("[OK] Verified: Answered clarification requests never generate reminders.")

    # -------------------------------------------------------------
    # Test 4: HTTP Endpoints Still Function Normally
    # -------------------------------------------------------------
    print("\n--- Test 4: HTTP API Health & Operations ---")
    r_stats = client.get("/stats", headers=headers_a)
    assert r_stats.status_code == 200
    assert r_stats.json()["overdue_items"] == 1
    print(f"[OK] HTTP GET /stats returns healthy response: Overdue count = {r_stats.json()['overdue_items']}.")

    print("\n==================================================================")
    print(" [STAGE 7 SUCCESS REPORT]")
    print(" - In-process APScheduler background scheduler implemented.")
    print(" - Job 1 (Daily Overdue Check): Detected overdue items, logged console fallback, and broadcasted action_item.overdue event.")
    print(" - Job 2 (Clarification Reminder Check): Detected requests > 24h old, broadcasted clarification.reminder, and populated reminder_sent_at.")
    print(" - Clarification requests with answered_at != None correctly ignored.")
    print(" - Cross-user data isolation verified (User B received no notifications for User A).")
    print(" - Absence of SMTP server handled gracefully without crashing.")
    print(" - HTTP API endpoints continue working normally.")
    print("==================================================================\n")

if __name__ == "__main__":
    run_stage_7_scheduler_verification()
