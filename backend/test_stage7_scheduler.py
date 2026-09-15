import os
import sys
import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app.models import User, Meeting, ActionItem, ClarificationRequest, ItemStatus, utc_now
from app.websocket_manager import manager
from app.config import settings
from app.scheduler import (
    run_daily_overdue_check,
    run_overdue_check,
    run_clarification_reminder_check,
    run_clarification_reminder,
    resolve_owner_email,
    send_email_notification,
    start_scheduler,
    shutdown_scheduler,
    _notified_overdue_today
)
from main import app

client = TestClient(app)

def run_stage7_tests():
    print("==================================================================")
    print("=== Stage 7: Testing APScheduler Background Jobs (12 Tests)   ===")
    print("==================================================================")

    # 1. Reset Database & In-memory sets
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _notified_overdue_today.clear()
    print("[INIT] Database reset.")

    # 2. Register User 1 & User 2
    r1 = client.post("/auth/register", json={"email": "priya@example.com", "password": "Password123!", "role": "member"})
    token1 = r1.json()["access_token"]
    u1_id = r1.json()["user"]["id"]
    h1 = {"Authorization": f"Bearer {token1}"}

    r2 = client.post("/auth/register", json={"email": "alex@example.com", "password": "Password123!", "role": "member"})
    token2 = r2.json()["access_token"]
    u2_id = r2.json()["user"]["id"]
    h2 = {"Authorization": f"Bearer {token2}"}

    print(f"[OK] Test users registered: User 1 ({u1_id}, priya@example.com), User 2 ({u2_id}, alex@example.com)")

    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        # Seed Meeting 1 for User 1
        m1 = Meeting(user_id=u1_id, title="Sprint Review", transcript_text="Sprint text", meeting_date=today, created_at=now)
        db.add(m1)
        db.flush()
        m1_id = m1.id

        # Seed Meeting 2 for User 2
        m2 = Meeting(user_id=u2_id, title="Operations Sync", transcript_text="Ops text", meeting_date=today, created_at=now)
        db.add(m2)
        db.flush()
        m2_id = m2.id

        # Seed Action Items for Overdue Tests (User 1)
        # Item 1: Overdue & in_progress
        ai_overdue = ActionItem(
            meeting_id=m1_id, task="Overdue in-progress task", owner="Priya",
            deadline=yesterday, priority="High", category="Engineering",
            status="in_progress", mention_count=1, created_at=now, updated_at=now
        )
        # Item 2: Overdue but done
        ai_done = ActionItem(
            meeting_id=m1_id, task="Overdue completed task", owner="Priya",
            deadline=yesterday, priority="Medium", category="Engineering",
            status="done", mention_count=1, created_at=now, updated_at=now
        )
        # Item 3: Future item
        ai_future = ActionItem(
            meeting_id=m1_id, task="Future scheduled task", owner="Priya",
            deadline=tomorrow, priority="Low", category="Engineering",
            status="todo", mention_count=1, created_at=now, updated_at=now
        )
        # Item 4: Null deadline item
        ai_null_deadline = ActionItem(
            meeting_id=m1_id, task="No deadline task", owner="Priya",
            deadline=None, priority="Low", category="General",
            status="todo", mention_count=1, created_at=now, updated_at=now
        )
        # Item 5: Overdue item for User 2
        ai_u2_overdue = ActionItem(
            meeting_id=m2_id, task="Alex overdue server audit", owner="Alex",
            deadline=yesterday, priority="High", category="Engineering",
            status="todo", mention_count=1, created_at=now, updated_at=now
        )

        db.add_all([ai_overdue, ai_done, ai_future, ai_null_deadline, ai_u2_overdue])
        db.commit()
        db.refresh(ai_overdue)
        db.refresh(ai_done)
        db.refresh(ai_future)
        db.refresh(ai_null_deadline)
        db.refresh(ai_u2_overdue)

        ai_overdue_id = ai_overdue.id
        ai_done_id = ai_done.id
        ai_future_id = ai_future.id
        ai_null_id = ai_null_deadline.id
        ai_u2_id = ai_u2_overdue.id

        # Seed Clarification Requests
        # Req 1: > 24h old, unanswered, unreminded (eligible)
        ai_clar1 = ActionItem(
            meeting_id=m1_id, task="Unclear marketing owner task", owner=None,
            deadline=None, priority="Medium", category="Marketing", needs_clarification=True,
            status="todo", mention_count=1, created_at=now - timedelta(hours=26), updated_at=now - timedelta(hours=26)
        )
        db.add(ai_clar1)
        db.flush()
        req_eligible = ClarificationRequest(
            action_item_id=ai_clar1.id,
            question_sent_at=now - timedelta(hours=26),
            answered_at=None,
            reminder_sent_at=None
        )

        # Req 2: < 24h old (younger, not eligible)
        ai_clar2 = ActionItem(
            meeting_id=m1_id, task="Recent unclear task", owner=None,
            deadline=None, priority="Low", category="General", needs_clarification=True,
            status="todo", mention_count=1, created_at=now - timedelta(hours=10), updated_at=now - timedelta(hours=10)
        )
        db.add(ai_clar2)
        db.flush()
        req_young = ClarificationRequest(
            action_item_id=ai_clar2.id,
            question_sent_at=now - timedelta(hours=10),
            answered_at=None,
            reminder_sent_at=None
        )

        # Req 3: > 24h old but already answered (not eligible)
        ai_clar3 = ActionItem(
            meeting_id=m1_id, task="Answered unclear task", owner="Priya",
            deadline=tomorrow, priority="High", category="Marketing", needs_clarification=False,
            is_confirmed=True, status="todo", mention_count=1, created_at=now - timedelta(hours=30), updated_at=now
        )
        db.add(ai_clar3)
        db.flush()
        req_answered = ClarificationRequest(
            action_item_id=ai_clar3.id,
            question_sent_at=now - timedelta(hours=30),
            answered_at=now - timedelta(hours=5),
            reminder_sent_at=None
        )

        # Req 4: > 24h old but already reminded (not eligible)
        ai_clar4 = ActionItem(
            meeting_id=m1_id, task="Already reminded unclear task", owner=None,
            deadline=None, priority="Medium", category="General", needs_clarification=True,
            status="todo", mention_count=1, created_at=now - timedelta(hours=40), updated_at=now - timedelta(hours=40)
        )
        db.add(ai_clar4)
        db.flush()
        req_already_reminded = ClarificationRequest(
            action_item_id=ai_clar4.id,
            question_sent_at=now - timedelta(hours=40),
            answered_at=None,
            reminder_sent_at=now - timedelta(hours=12)
        )

        db.add_all([req_eligible, req_young, req_answered, req_already_reminded])
        db.commit()
        db.refresh(req_eligible)
        db.refresh(req_young)
        db.refresh(req_answered)
        db.refresh(req_already_reminded)

        req_eligible_id = req_eligible.id
        req_young_id = req_young.id
        req_answered_id = req_answered.id
        req_reminded_id = req_already_reminded.id
        ai_clar1_id = ai_clar1.id

        print(f"[OK] Seeded Overdue ActionItems: [#{ai_overdue_id} (overdue), #{ai_done_id} (done), #{ai_future_id} (future), #{ai_null_id} (null deadline), #{ai_u2_id} (U2 overdue)]")
        print(f"[OK] Seeded ClarificationRequests: [#{req_eligible_id} (eligible), #{req_young_id} (young), #{req_answered_id} (answered), #{req_reminded_id} (reminded)]")

    finally:
        db.close()

    # -------------------------------------------------------------
    # TEST 1: Overdue Detection
    # -------------------------------------------------------------
    print("\n--- [TEST 1] Overdue Item Detection ---")
    _notified_overdue_today.clear()
    asyncio.run(run_overdue_check())
    assert (ai_overdue_id, today.isoformat()) in _notified_overdue_today
    print(f"[PASS] Test 1: Overdue item #{ai_overdue_id} detected successfully.")

    # -------------------------------------------------------------
    # TEST 2: Completed Overdue Item Ignored
    # -------------------------------------------------------------
    print("\n--- [TEST 2] Completed Overdue Item Ignored (status='done') ---")
    assert (ai_done_id, today.isoformat()) not in _notified_overdue_today
    print(f"[PASS] Test 2: Done item #{ai_done_id} with past deadline was not marked overdue.")

    # -------------------------------------------------------------
    # TEST 3: Future Item Ignored
    # -------------------------------------------------------------
    print("\n--- [TEST 3] Future Item Ignored (deadline > today) ---")
    assert (ai_future_id, today.isoformat()) not in _notified_overdue_today
    print(f"[PASS] Test 3: Future item #{ai_future_id} was not marked overdue.")

    # -------------------------------------------------------------
    # TEST 4: Null Deadline Ignored
    # -------------------------------------------------------------
    print("\n--- [TEST 4] Null Deadline Ignored ---")
    assert (ai_null_id, today.isoformat()) not in _notified_overdue_today
    print(f"[PASS] Test 4: Null-deadline item #{ai_null_id} was not marked overdue.")

    # -------------------------------------------------------------
    # TEST 5: Overdue WebSocket Notification
    # -------------------------------------------------------------
    print("\n--- [TEST 5] Overdue WebSocket Notification (SMTP Unconfigured Path) ---")
    _notified_overdue_today.clear()
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws1:
        asyncio.run(run_overdue_check())
        msg = ws1.receive_json()
        print(f"WS Overdue Received: {json.dumps(msg, indent=2)}")
        assert msg["event"] == "action_item.overdue"
        assert msg["data"]["id"] == ai_overdue_id
        assert msg["data"]["task"] == "Overdue in-progress task"
        assert msg["data"]["status"] == "in_progress"
    print("[PASS] Test 5: action_item.overdue broadcast received with accurate payload.")

    # -------------------------------------------------------------
    # TEST 6: User Isolation in Background Jobs
    # -------------------------------------------------------------
    print("\n--- [TEST 6] User Isolation in Background Overdue Job ---")
    _notified_overdue_today.clear()
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws_u1, \
         client.websocket_connect(f"/ws/updates?token={token2}") as ws_u2:

        asyncio.run(run_overdue_check())

        # User 1 receives User 1 overdue event
        msg_u1 = ws_u1.receive_json()
        assert msg_u1["event"] == "action_item.overdue"
        assert msg_u1["data"]["id"] == ai_overdue_id

        # User 2 receives User 2 overdue event
        msg_u2 = ws_u2.receive_json()
        assert msg_u2["event"] == "action_item.overdue"
        assert msg_u2["data"]["id"] == ai_u2_id
        assert msg_u2["data"]["owner"] == "Alex"
    print("[PASS] Test 6: Strict user isolation verified for background jobs.")

    # -------------------------------------------------------------
    # TEST 7: Clarification Older Than 24h (Eligible)
    # -------------------------------------------------------------
    print("\n--- [TEST 7] Clarification Older Than 24h Triggers Reminder ---")
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws1:
        asyncio.run(run_clarification_reminder_check())

        msg = ws1.receive_json()
        print(f"WS Clarification Reminder Received: {json.dumps(msg, indent=2)}")
        assert msg["event"] == "clarification.reminder"
        assert msg["data"]["action_item_id"] == ai_clar1_id
        assert msg["data"]["reminder_sent_at"] is not None

        db = SessionLocal()
        try:
            req_db = db.query(ClarificationRequest).filter(ClarificationRequest.id == req_eligible_id).first()
            assert req_db.reminder_sent_at is not None
            print(f"[OK] ClarificationRequest #{req_eligible_id} reminder_sent_at updated in DB: {req_db.reminder_sent_at}")
        finally:
            db.close()
    print("[PASS] Test 7: Eligible clarification request (>24h) reminded and updated in DB.")

    # -------------------------------------------------------------
    # TEST 8: Clarification Younger Than 24h (Ignored)
    # -------------------------------------------------------------
    print("\n--- [TEST 8] Clarification Younger Than 24h Ignored ---")
    db = SessionLocal()
    try:
        req_young_db = db.query(ClarificationRequest).filter(ClarificationRequest.id == req_young_id).first()
        assert req_young_db.reminder_sent_at is None
        print(f"[OK] ClarificationRequest #{req_young_id} (10h old) reminder_sent_at is still None.")
    finally:
        db.close()
    print("[PASS] Test 8: Younger clarification requests not reminded.")

    # -------------------------------------------------------------
    # TEST 9: Already Answered Clarification Ignored
    # -------------------------------------------------------------
    print("\n--- [TEST 9] Already Answered Clarification Ignored ---")
    db = SessionLocal()
    try:
        req_ans_db = db.query(ClarificationRequest).filter(ClarificationRequest.id == req_answered_id).first()
        assert req_ans_db.reminder_sent_at is None
    finally:
        db.close()
    print("[PASS] Test 9: Answered clarification requests not reminded.")

    # -------------------------------------------------------------
    # TEST 10: Already Reminded Clarification Not Repeated
    # -------------------------------------------------------------
    print("\n--- [TEST 10] Already Reminded Clarification Not Repeated ---")
    # Run clarification job again; eligible request was already reminded in Test 7, so 0 reminders should fire
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws1:
        asyncio.run(run_clarification_reminder_check())
        # Ping to confirm no clarification events were placed in queue
        ws1.send_text("ping")
        resp = ws1.receive_json()
        assert resp == {"event": "pong"}
    print("[PASS] Test 10: Previously reminded requests are not reminded again.")

    # -------------------------------------------------------------
    # TEST 11: WebSocket Broadcast Failure Isolation
    # -------------------------------------------------------------
    print("\n--- [TEST 11] WebSocket Broadcast Failure Isolation ---")
    with patch("app.websocket_manager.manager.broadcast_to_user", side_effect=Exception("Simulated WS Network Drop")):
        # Overdue check should handle the WS exception gracefully without crashing
        _notified_overdue_today.clear()
        try:
            asyncio.run(run_overdue_check())
            print("[OK] Overdue job completed safely despite WS network drop.")
        except Exception as e:
            assert False, f"Scheduler crashed on WS exception: {e}"
    print("[PASS] Test 11: WebSocket failure did not crash background scheduler.")

    # -------------------------------------------------------------
    # TEST 12: Scheduler Lifecycle (Startup & Clean Shutdown)
    # -------------------------------------------------------------
    print("\n--- [TEST 12] Scheduler Startup & Shutdown Lifecycle ---")
    # Start scheduler in test mode
    sched = start_scheduler(test_mode=True)
    assert sched.running is True
    print(f"[OK] Scheduler started successfully: running={sched.running}, jobs={len(sched.get_jobs())}")

    # Ensure idempotency: starting again returns same running scheduler
    sched2 = start_scheduler(test_mode=True)
    assert sched2 == sched

    # Clean shutdown
    shutdown_scheduler()
    from app.scheduler import scheduler as current_sched
    assert current_sched is None
    print("[PASS] Test 12: Scheduler starts and shuts down cleanly with zero dangling resources.")

    # -------------------------------------------------------------
    # BONUS / SECTION 9 TEST: SMTP Sending Function & Fallback
    # -------------------------------------------------------------
    print("\n--- [SMTP Integration Testing] Configured vs Unconfigured ---")
    # 1. Unconfigured SMTP
    with patch("app.config.settings.SMTP_HOST", None):
        res_unconf = send_email_notification("test@clarifier.com", "Subject", "Body")
        assert res_unconf is False
        print("[OK] Unconfigured SMTP safely falls back to False without raising exceptions.")

    # 2. Configured SMTP (Mocked)
    with patch("app.config.settings.SMTP_HOST", "smtp.example.com"), \
         patch("app.config.settings.SMTP_USERNAME", "mailer"), \
         patch("app.config.settings.SMTP_PASSWORD", "secret"), \
         patch("smtplib.SMTP") as mock_smtp:
        
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance

        res_conf = send_email_notification("priya@example.com", "Test Subject", "Test Body")
        assert res_conf is True
        mock_instance.sendmail.assert_called_once()
        print("[OK] Configured SMTP calls smtplib and returns True successfully.")

    print("\n==================================================================")
    print("=== ALL 12 STAGE 7 SCHEDULER TESTS PASSED SUCCESSFULLY ===")
    print("==================================================================")
    return True

if __name__ == "__main__":
    run_stage7_tests()
