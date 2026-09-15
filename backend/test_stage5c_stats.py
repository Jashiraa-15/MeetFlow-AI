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

def run_stage5c_tests():
    print("==================================================================")
    print("=== Stage 5C: Testing Stats Endpoint (GET /stats - 12 Tests) ===")
    print("==================================================================")

    # 1. Reset Database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[INIT] Database reset.")

    # 2. Register User 1 (Member with rich data), User 2 (Member with isolated data), User 3 (Fresh user with 0 items)
    r1 = client.post("/auth/register", json={"email": "u1.analytics@clarifier.com", "password": "Password123!", "role": "member"})
    u1_id = r1.json()["user"]["id"]
    h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}

    r2 = client.post("/auth/register", json={"email": "u2.isolated@clarifier.com", "password": "Password123!", "role": "member"})
    u2_id = r2.json()["user"]["id"]
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    r3 = client.post("/auth/register", json={"email": "u3.empty@clarifier.com", "password": "Password123!", "role": "member"})
    u3_id = r3.json()["user"]["id"]
    h3 = {"Authorization": f"Bearer {r3.json()['access_token']}"}

    print(f"[OK] Users registered: U1 ({u1_id}), U2 ({u2_id}), U3 ({u3_id})")

    # 3. Seed User 1 Data (3 meetings, 10 action items)
    today = date.today()
    yesterday = today - timedelta(days=2)
    tomorrow = today + timedelta(days=2)
    now = utc_now()

    db = SessionLocal()
    try:
        # U1 - Meeting 1
        m1 = Meeting(user_id=u1_id, title="Sprint Review", transcript_text="Sprint text", meeting_date=today, created_at=now)
        # U1 - Meeting 2
        m2 = Meeting(user_id=u1_id, title="Product Roadmap", transcript_text="Roadmap text", meeting_date=today, created_at=now)
        # U1 - Meeting 3
        m3 = Meeting(user_id=u1_id, title="Marketing Sync", transcript_text="Marketing text", meeting_date=today, created_at=now)
        db.add_all([m1, m2, m3])
        db.flush()

        # Seed 10 action items for User 1:
        # Priya: 4 items
        # - Item 1: Priya, done, yesterday (NOT overdue because done)
        # - Item 2: Priya, todo, tomorrow (NOT overdue because future)
        # - Item 3: Priya, in_progress, yesterday (OVERDUE #1)
        # - Item 4: Priya, todo, tomorrow, needs_clarification=True (CLARIFICATION #1)
        items_u1 = [
            ActionItem(meeting_id=m1.id, task="Priya Task 1", owner="Priya", deadline=yesterday, status="done", needs_clarification=False, created_at=now, updated_at=now),
            ActionItem(meeting_id=m1.id, task="Priya Task 2", owner="Priya", deadline=tomorrow, status="todo", needs_clarification=False, created_at=now, updated_at=now),
            ActionItem(meeting_id=m1.id, task="Priya Task 3", owner="Priya", deadline=yesterday, status="in_progress", needs_clarification=False, created_at=now, updated_at=now),
            ActionItem(meeting_id=m1.id, task="Priya Task 4", owner="Priya", deadline=tomorrow, status="todo", needs_clarification=True, created_at=now, updated_at=now),

            # Sam: 3 items
            # - Item 5: Sam, todo, yesterday (OVERDUE #2)
            # - Item 6: Sam, in_progress, tomorrow, needs_clarification=False
            # - Item 7: Sam, done, yesterday (NOT overdue because done)
            ActionItem(meeting_id=m2.id, task="Sam Task 1", owner="Sam", deadline=yesterday, status="todo", needs_clarification=False, created_at=now, updated_at=now),
            ActionItem(meeting_id=m2.id, task="Sam Task 2", owner="Sam", deadline=tomorrow, status="in_progress", needs_clarification=False, created_at=now, updated_at=now),
            ActionItem(meeting_id=m2.id, task="Sam Task 3", owner="Sam", deadline=yesterday, status="done", needs_clarification=False, created_at=now, updated_at=now),

            # Rahul: 1 item
            # - Item 8: Rahul, todo, tomorrow, needs_clarification=False
            ActionItem(meeting_id=m3.id, task="Rahul Task 1", owner="Rahul", deadline=tomorrow, status="todo", needs_clarification=False, created_at=now, updated_at=now),

            # Unassigned (owner=None): 2 items
            # - Item 9: None, no deadline, needs_clarification=True (CLARIFICATION #2)
            # - Item 10: None, no deadline, needs_clarification=False
            ActionItem(meeting_id=m3.id, task="Unassigned Task 1", owner=None, deadline=None, status="todo", needs_clarification=True, created_at=now, updated_at=now),
            ActionItem(meeting_id=m3.id, task="Unassigned Task 2", owner=None, deadline=None, status="todo", needs_clarification=False, created_at=now, updated_at=now),
        ]
        db.add_all(items_u1)

        # Seed User 2 (1 meeting, 2 action items for Alex)
        m4 = Meeting(user_id=u2_id, title="User 2 Secret Meeting", transcript_text="U2 text", meeting_date=today, created_at=now)
        db.add(m4)
        db.flush()
        items_u2 = [
            ActionItem(meeting_id=m4.id, task="Alex Task 1", owner="Alex", deadline=yesterday, status="todo", needs_clarification=True, created_at=now, updated_at=now),
            ActionItem(meeting_id=m4.id, task="Alex Task 2", owner="Alex", deadline=tomorrow, status="todo", needs_clarification=False, created_at=now, updated_at=now),
        ]
        db.add_all(items_u2)
        db.commit()

        print(f"[OK] Fixture Seeded: U1 has 3 meetings, 10 tasks (Priya:4, Sam:3, Rahul:1, None:2; Clarification:2; Overdue:2). U2 has 1 meeting, 2 tasks.")
    finally:
        db.close()

    # -------------------------------------------------------------
    # TEST 1: Retrieve stats for User 1 & verify structure
    # -------------------------------------------------------------
    print("\n--- [TEST 1] GET /stats Response Structure ---")
    res1 = client.get("/stats", headers=h1)
    assert res1.status_code == 200
    stats1 = res1.json()
    print("User 1 Stats JSON:")
    print(json.dumps(stats1, indent=2))

    assert "total_meetings" in stats1
    assert "total_action_items" in stats1
    assert "clarification_percentage" in stats1
    assert "overdue_count" in stats1
    assert "per_owner" in stats1
    assert "workload" in stats1
    print("[PASS] Test 1: Stats response contains all required fields.")

    # -------------------------------------------------------------
    # TEST 2: Verify total_meetings calculation
    # -------------------------------------------------------------
    print("\n--- [TEST 2] Total Meetings Verification ---")
    assert stats1["total_meetings"] == 3, f"Expected 3 meetings, got {stats1['total_meetings']}"
    print("[PASS] Test 2: total_meetings = 3.")

    # -------------------------------------------------------------
    # TEST 3: Verify total_action_items calculation
    # -------------------------------------------------------------
    print("\n--- [TEST 3] Total Action Items Verification ---")
    assert stats1["total_action_items"] == 10, f"Expected 10 action items, got {stats1['total_action_items']}"
    print("[PASS] Test 3: total_action_items = 10.")

    # -------------------------------------------------------------
    # TEST 4: Verify clarification_percentage calculation
    # -------------------------------------------------------------
    print("\n--- [TEST 4] Clarification Percentage Verification ---")
    # 2 items out of 10 -> 20.0%
    assert stats1["clarification_percentage"] == 20.0, f"Expected 20.0%, got {stats1['clarification_percentage']}"
    print("[PASS] Test 4: clarification_percentage = 20.0%.")

    # -------------------------------------------------------------
    # TEST 5: Verify overdue_count calculation (Mixed Statuses)
    # -------------------------------------------------------------
    print("\n--- [TEST 5] Overdue Items Verification ---")
    # Item 3 (in_progress, past) and Item 5 (todo, past) = 2 overdue items. Items 1 & 7 are done, so NOT overdue.
    assert stats1["overdue_count"] == 2, f"Expected 2 overdue items, got {stats1['overdue_count']}"
    assert stats1["overdue_items"] == 2
    print("[PASS] Test 5: overdue_count = 2 (correctly ignores past items with status='done').")

    # -------------------------------------------------------------
    # TEST 6: Verify per_owner breakdown dictionary
    # -------------------------------------------------------------
    print("\n--- [TEST 6] Per-Owner Breakdown Verification ---")
    per_owner = stats1["per_owner"]
    assert per_owner["Priya"] == 4, f"Expected Priya: 4, got {per_owner.get('Priya')}"
    assert per_owner["Sam"] == 3, f"Expected Sam: 3, got {per_owner.get('Sam')}"
    assert per_owner["Rahul"] == 1, f"Expected Rahul: 1, got {per_owner.get('Rahul')}"
    print("[PASS] Test 6: per_owner counts match exactly (Priya:4, Sam:3, Rahul:1).")

    # -------------------------------------------------------------
    # TEST 7: Verify unassigned items are NOT in per_owner
    # -------------------------------------------------------------
    print("\n--- [TEST 7] Null/Unassigned Owner Exclusion ---")
    assert None not in per_owner
    assert "None" not in per_owner
    assert "null" not in per_owner
    print("[PASS] Test 7: Null/Unassigned owner correctly excluded from named owner counts.")

    # -------------------------------------------------------------
    # TEST 8: Zero-Action-Item Case (Division by Zero Safety)
    # -------------------------------------------------------------
    print("\n--- [TEST 8] Zero-Action-Item Case (User 3) ---")
    res3 = client.get("/stats", headers=h3)
    assert res3.status_code == 200
    stats3 = res3.json()
    print("User 3 (Empty) Stats JSON:")
    print(json.dumps(stats3, indent=2))
    assert stats3["total_meetings"] == 0
    assert stats3["total_action_items"] == 0
    assert stats3["clarification_percentage"] == 0.0
    assert stats3["overdue_count"] == 0
    assert stats3["per_owner"] == {}
    assert stats3["workload"] == []
    print("[PASS] Test 8: Zero-action-item user safely returned 0.0% without division-by-zero error.")

    # -------------------------------------------------------------
    # TEST 9: Cross-User Isolation (User 2)
    # -------------------------------------------------------------
    print("\n--- [TEST 9] Cross-User Isolation (User 2) ---")
    res2 = client.get("/stats", headers=h2)
    assert res2.status_code == 200
    stats2 = res2.json()
    print("User 2 Stats JSON:")
    print(json.dumps(stats2, indent=2))
    assert stats2["total_meetings"] == 1
    assert stats2["total_action_items"] == 2
    assert stats2["clarification_percentage"] == 50.0  # 1 out of 2 = 50.0%
    assert stats2["overdue_count"] == 1
    assert stats2["per_owner"] == {"Alex": 2}
    # Verify User 1's owners do not leak into User 2
    assert "Priya" not in stats2["per_owner"]
    print("[PASS] Test 9: User 2 stats strictly isolated.")

    # -------------------------------------------------------------
    # TEST 10 & 11: Missing and Invalid JWT -> 401
    # -------------------------------------------------------------
    print("\n--- [TEST 10 & 11] Unauthenticated and Invalid JWT (401) ---")
    r_unauth = client.get("/stats")
    assert r_unauth.status_code == 401
    r_bad = client.get("/stats", headers={"Authorization": "Bearer bad.token"})
    assert r_bad.status_code == 401
    print("[PASS] Test 10 & 11: 401 returned for missing/invalid auth.")

    # -------------------------------------------------------------
    # TEST 12: Manual SQL Cross-Check
    # -------------------------------------------------------------
    print("\n--- [TEST 12] Manual SQLite Row Verification ---")
    db = SessionLocal()
    try:
        raw_meetings = db.query(Meeting).filter(Meeting.user_id == u1_id).count()
        assert raw_meetings == stats1["total_meetings"]
        
        raw_items = (
            db.query(ActionItem)
            .join(Meeting, ActionItem.meeting_id == Meeting.id)
            .filter(Meeting.user_id == u1_id)
            .count()
        )
        assert raw_items == stats1["total_action_items"]
        print("[PASS] Test 12: Direct SQL row counts match API calculations 1-to-1.")
    finally:
        db.close()

    print("\n==================================================================")
    print("=== ALL 12 STAGE 5C STATS TESTS PASSED ===")
    print("==================================================================")
    return True

if __name__ == "__main__":
    run_stage5c_tests()
