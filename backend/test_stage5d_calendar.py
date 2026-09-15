import os
import sys
import json
from datetime import date, timedelta

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app.models import User, Meeting, ActionItem, utc_now
from main import app

client = TestClient(app)

def run_stage5d_tests():
    print("==================================================================")
    print("=== Stage 5D: Testing Calendar Endpoint (GET /calendar - 12 Tests) ===")
    print("==================================================================")

    # 1. Reset Database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[INIT] Database reset.")

    # 2. Register User 1 (Main test user), User 2 (Isolated user), User 3 (Empty user)
    r1 = client.post("/auth/register", json={"email": "u1.calendar@clarifier.com", "password": "Password123!", "role": "member"})
    u1_id = r1.json()["user"]["id"]
    h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}

    r2 = client.post("/auth/register", json={"email": "u2.isolated@clarifier.com", "password": "Password123!", "role": "member"})
    u2_id = r2.json()["user"]["id"]
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    r3 = client.post("/auth/register", json={"email": "u3.empty@clarifier.com", "password": "Password123!", "role": "member"})
    u3_id = r3.json()["user"]["id"]
    h3 = {"Authorization": f"Bearer {r3.json()['access_token']}"}

    print(f"[OK] Test users registered: U1 ({u1_id}), U2 ({u2_id}), U3 ({u3_id})")

    # 3. Seed Calendar Fixtures for User 1 & User 2
    today = date.today()
    past_date_1 = today - timedelta(days=5)
    past_date_2 = today - timedelta(days=2)
    today_str = today.isoformat()
    future_date_1 = today + timedelta(days=3)
    future_date_2 = today + timedelta(days=7)
    now = utc_now()

    db = SessionLocal()
    try:
        # User 1 Meeting
        m1 = Meeting(user_id=u1_id, title="Sprint & Launch Sync", transcript_text="Sprint text", meeting_date=today, created_at=now)
        db.add(m1)
        db.flush()
        m1_id = m1.id

        # Fixture Items for User 1:
        # Date past_date_1: 1 item (Past deadline, status='done') -> MUST appear
        item_past_done = ActionItem(
            meeting_id=m1_id, task="Archive old quarterly data", owner="Sam",
            deadline=past_date_1, status="done", priority="Low", category="General",
            confidence=0.9, needs_clarification=False, is_confirmed=True, created_at=now, updated_at=now
        )
        # Date past_date_2: 1 item (Past deadline, status='todo') -> MUST appear
        item_past_todo = ActionItem(
            meeting_id=m1_id, task="Submit security audit feedback", owner="Priya",
            deadline=past_date_2, status="todo", priority="High", category="Engineering",
            confidence=0.9, needs_clarification=False, is_confirmed=True, created_at=now, updated_at=now
        )
        # Date future_date_1 (same date): 2 items grouped together -> MUST appear together
        item_future_1a = ActionItem(
            meeting_id=m1_id, task="Draft press release announcement", owner="Priya",
            deadline=future_date_1, status="todo", priority="High", category="Marketing",
            confidence=0.95, needs_clarification=False, is_confirmed=True, created_at=now, updated_at=now
        )
        item_future_1b = ActionItem(
            meeting_id=m1_id, task="Prepare social media assets", owner="Sam",
            deadline=future_date_1, status="in_progress", priority="Medium", category="Marketing",
            confidence=0.90, needs_clarification=False, is_confirmed=True, created_at=now, updated_at=now
        )
        # Date future_date_2: 1 item (Future deadline, status='todo') -> MUST appear
        item_future_2 = ActionItem(
            meeting_id=m1_id, task="Send launch email to subscribers", owner="Rahul",
            deadline=future_date_2, status="todo", priority="High", category="Marketing",
            confidence=0.90, needs_clarification=False, is_confirmed=True, created_at=now, updated_at=now
        )
        # Null Deadline: 2 items (Must be strictly EXCLUDED from calendar)
        item_null_1 = ActionItem(
            meeting_id=m1_id, task="Update pricing table CSS", owner=None,
            deadline=None, status="todo", priority="Medium", category="Engineering",
            confidence=0.40, needs_clarification=True, is_confirmed=False, created_at=now, updated_at=now
        )
        item_null_2 = ActionItem(
            meeting_id=m1_id, task="Review backlog items", owner="Priya",
            deadline=None, status="todo", priority="Low", category="General",
            confidence=0.50, needs_clarification=True, is_confirmed=False, created_at=now, updated_at=now
        )

        db.add_all([item_past_done, item_past_todo, item_future_1a, item_future_1b, item_future_2, item_null_1, item_null_2])

        # User 2 Meeting & Items (Isolated data)
        m2 = Meeting(user_id=u2_id, title="User 2 Project", transcript_text="U2 text", meeting_date=today, created_at=now)
        db.add(m2)
        db.flush()
        item_u2 = ActionItem(
            meeting_id=m2.id, task="Alex confidential server maintenance", owner="Alex",
            deadline=future_date_1, status="todo", priority="High", category="Engineering",
            confidence=0.95, needs_clarification=False, is_confirmed=True, created_at=now, updated_at=now
        )
        db.add(item_u2)
        db.commit()

        print(f"[OK] Seeded calendar fixtures: U1 has 5 deadline items across 4 dates, 2 null-deadline items. U2 has 1 item on {future_date_1.isoformat()}.")
    finally:
        db.close()

    # -------------------------------------------------------------
    # TEST 1: Retrieve calendar for User 1 & verify non-null items returned
    # -------------------------------------------------------------
    print("\n--- [TEST 1] GET /calendar Response for User 1 ---")
    res1 = client.get("/calendar", headers=h1)
    assert res1.status_code == 200
    cal_data = res1.json()
    print("User 1 Calendar Data (JSON):")
    print(json.dumps(cal_data, indent=2))

    total_cal_tasks = sum(len(tasks) for tasks in cal_data.values())
    assert total_cal_tasks == 5, f"Expected 5 non-null deadline tasks, got {total_cal_tasks}"
    print(f"[PASS] Test 1: Exactly 5 deadline tasks returned across dates.")

    # -------------------------------------------------------------
    # TEST 2: Null-deadline items are strictly excluded
    # -------------------------------------------------------------
    print("\n--- [TEST 2] Null-Deadline Exclusion ---")
    all_returned_tasks = [task["task"] for tasks in cal_data.values() for task in tasks]
    assert "Update pricing table CSS" not in all_returned_tasks
    assert "Review backlog items" not in all_returned_tasks
    print("[PASS] Test 2: Null-deadline items successfully excluded.")

    # -------------------------------------------------------------
    # TEST 3: Multiple tasks grouped under the same date
    # -------------------------------------------------------------
    print(f"\n--- [TEST 3] Date Grouping on {future_date_1.isoformat()} ---")
    k_future1 = future_date_1.isoformat()
    assert k_future1 in cal_data
    tasks_on_future1 = cal_data[k_future1]
    assert len(tasks_on_future1) == 2, f"Expected 2 tasks on {k_future1}, got {len(tasks_on_future1)}"
    assert any("press release" in t["task"].lower() for t in tasks_on_future1)
    assert any("social media" in t["task"].lower() for t in tasks_on_future1)
    print(f"[PASS] Test 3: Multiple tasks correctly grouped under {k_future1}.")

    # -------------------------------------------------------------
    # TEST 4: Different dates create separate groups
    # -------------------------------------------------------------
    print("\n--- [TEST 4] Separate Date Keys ---")
    assert len(cal_data.keys()) == 4, f"Expected 4 distinct date keys, got {len(cal_data.keys())}"
    expected_dates = {past_date_1.isoformat(), past_date_2.isoformat(), future_date_1.isoformat(), future_date_2.isoformat()}
    assert set(cal_data.keys()) == expected_dates
    print(f"[PASS] Test 4: All 4 distinct dates generated separate groups: {sorted(cal_data.keys())}.")

    # -------------------------------------------------------------
    # TEST 5: Past deadlines are returned
    # -------------------------------------------------------------
    print(f"\n--- [TEST 5] Past Deadlines Returned ({past_date_2.isoformat()}) ---")
    assert past_date_2.isoformat() in cal_data
    assert cal_data[past_date_2.isoformat()][0]["task"] == "Submit security audit feedback"
    print("[PASS] Test 5: Past deadline tasks correctly included.")

    # -------------------------------------------------------------
    # TEST 6: Done items with deadlines are returned
    # -------------------------------------------------------------
    print(f"\n--- [TEST 6] Done Items with Deadlines Returned ({past_date_1.isoformat()}) ---")
    assert past_date_1.isoformat() in cal_data
    done_task = cal_data[past_date_1.isoformat()][0]
    assert done_task["status"] == "done"
    assert done_task["task"] == "Archive old quarterly data"
    print("[PASS] Test 6: Completed items with deadlines are returned in calendar.")

    # -------------------------------------------------------------
    # TEST 7: Future deadlines returned
    # -------------------------------------------------------------
    print(f"\n--- [TEST 7] Future Deadlines Returned ({future_date_2.isoformat()}) ---")
    assert future_date_2.isoformat() in cal_data
    assert cal_data[future_date_2.isoformat()][0]["owner"] == "Rahul"
    print("[PASS] Test 7: Future deadline tasks included.")

    # -------------------------------------------------------------
    # TEST 8: Chronological Ordering of Date Keys
    # -------------------------------------------------------------
    print("\n--- [TEST 8] Chronological Ordering ---")
    date_keys = list(cal_data.keys())
    assert date_keys == sorted(date_keys), f"Dates are not in chronological order: {date_keys}"
    print(f"[PASS] Test 8: Calendar dates returned in chronological order: {date_keys}.")

    # -------------------------------------------------------------
    # TEST 9: Cross-User Isolation
    # -------------------------------------------------------------
    print("\n--- [TEST 9] Cross-User Isolation (User 2) ---")
    # Verify User 1 calendar doesn't have Alex's task
    assert not any("confidential server maintenance" in t["task"] for tasks in cal_data.values() for t in tasks)
    
    # Query User 2 calendar
    res2 = client.get("/calendar", headers=h2)
    assert res2.status_code == 200
    cal_u2 = res2.json()
    print("User 2 Calendar Data (JSON):")
    print(json.dumps(cal_u2, indent=2))
    assert len(cal_u2) == 1
    assert k_future1 in cal_u2
    assert len(cal_u2[k_future1]) == 1
    assert cal_u2[k_future1][0]["owner"] == "Alex"
    # Verify User 2 does not receive User 1's tasks on the same date
    assert not any("press release" in t["task"].lower() for t in cal_u2[k_future1])
    print("[PASS] Test 9: Multi-tenant calendar isolation strictly verified.")

    # -------------------------------------------------------------
    # TEST 10 & 11: Missing and Invalid JWT (401)
    # -------------------------------------------------------------
    print("\n--- [TEST 10 & 11] Unauthenticated and Invalid Auth (401) ---")
    r_unauth = client.get("/calendar")
    assert r_unauth.status_code == 401
    r_bad = client.get("/calendar", headers={"Authorization": "Bearer bad.token.here"})
    assert r_bad.status_code == 401
    print("[PASS] Test 10 & 11: 401 returned for unauthenticated/invalid requests.")

    # -------------------------------------------------------------
    # TEST 12: User with no deadline items receives {}
    # -------------------------------------------------------------
    print("\n--- [TEST 12] Empty Calendar for User with No Deadlines ---")
    res3 = client.get("/calendar", headers=h3)
    assert res3.status_code == 200
    assert res3.json() == {}, f"Expected empty dict {{}}, got {res3.json()}"
    print("[PASS] Test 12: User without deadline items returned empty calendar {}.")

    print("\n==================================================================")
    print("=== ALL 12 STAGE 5D CALENDAR TESTS PASSED ===")
    print("==================================================================")
    return True

if __name__ == "__main__":
    run_stage5d_tests()
