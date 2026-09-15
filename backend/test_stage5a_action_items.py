import os
import sys
import json
from datetime import date, timedelta

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app.models import User, Meeting, ActionItem, ClarificationRequest, ItemStatus, ItemPriority, utc_now
from main import app

client = TestClient(app)

def run_stage5a_tests():
    print("==================================================================")
    print("=== Stage 5A: Testing Action Items Endpoints (17 Tests) ===")
    print("==================================================================")

    # 1. Reset DB
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[INIT] Database reset.")

    # 2. Setup Test Users
    # Member 1
    r_u1 = client.post("/auth/register", json={"email": "member1@clarifier.com", "password": "Password123!", "role": "member"})
    token1 = r_u1.json()["access_token"]
    u1_id = r_u1.json()["user"]["id"]
    h1 = {"Authorization": f"Bearer {token1}"}

    # Member 2
    r_u2 = client.post("/auth/register", json={"email": "member2@clarifier.com", "password": "Password123!", "role": "member"})
    token2 = r_u2.json()["access_token"]
    u2_id = r_u2.json()["user"]["id"]
    h2 = {"Authorization": f"Bearer {token2}"}

    # Admin User
    r_admin = client.post("/auth/register", json={"email": "admin@clarifier.com", "password": "AdminPassword123!", "role": "admin"})
    token_admin = r_admin.json()["access_token"]
    admin_id = r_admin.json()["user"]["id"]
    h_admin = {"Authorization": f"Bearer {token_admin}"}

    print(f"[OK] Users created: Member 1 ({u1_id}), Member 2 ({u2_id}), Admin ({admin_id})")

    # 3. Seed Meetings and Action Items for Member 1 & Member 2
    db = SessionLocal()
    today = date.today()
    yesterday = today - timedelta(days=2)
    tomorrow = today + timedelta(days=2)
    now = utc_now()

    try:
        # Meeting for Member 1
        m1 = Meeting(user_id=u1_id, title="Sprint Planning", transcript_text="Sprint planning transcript", meeting_date=today, created_at=now)
        db.add(m1)
        db.flush()

        # Item 1: Confirmed, Marketing, Priya, In Progress
        item1 = ActionItem(
            meeting_id=m1.id, task="Write product launch press release", owner="Priya",
            deadline=tomorrow, priority="High", category="Marketing", confidence=0.95,
            needs_clarification=False, is_confirmed=True, status="in_progress", mention_count=1,
            created_at=now, updated_at=now
        )
        # Item 2: Needs Clarification, Engineering, No owner, No deadline
        item2 = ActionItem(
            meeting_id=m1.id, task="Update pricing tier database schema", owner=None,
            deadline=None, priority="Medium", category="Engineering", confidence=0.40,
            needs_clarification=True, is_confirmed=False, status="todo", mention_count=1,
            created_at=now, updated_at=now
        )
        # Item 3: Overdue item, General, Sam, Todo, Deadline = Yesterday
        item3 = ActionItem(
            meeting_id=m1.id, task="Prepare monthly analytics report", owner="Sam",
            deadline=yesterday, priority="Low", category="General", confidence=0.90,
            needs_clarification=False, is_confirmed=True, status="todo", mention_count=1,
            created_at=now, updated_at=now
        )
        # Item 4: Similar to Item 1 for fuzzy candidate testing
        item4 = ActionItem(
            meeting_id=m1.id, task="Write product launch press release for tech media", owner="Priya",
            deadline=tomorrow, priority="High", category="Marketing", confidence=0.85,
            needs_clarification=False, is_confirmed=True, status="todo", mention_count=1,
            created_at=now, updated_at=now
        )

        db.add_all([item1, item2, item3, item4])
        db.flush()

        # Clarification request for Item 2
        cr2 = ClarificationRequest(action_item_id=item2.id, question_sent_at=now)
        db.add(cr2)

        # Meeting for Member 2
        m2 = Meeting(user_id=u2_id, title="User 2 Meeting", transcript_text="User 2 transcript", meeting_date=today, created_at=now)
        db.add(m2)
        db.flush()

        # Item 5: Member 2's item
        item5 = ActionItem(
            meeting_id=m2.id, task="Member 2 private task", owner="Alex",
            deadline=tomorrow, priority="Medium", category="Engineering", confidence=0.90,
            needs_clarification=True, is_confirmed=False, status="todo", mention_count=1,
            created_at=now, updated_at=now
        )
        db.add(item5)
        db.commit()

        m1_id = m1.id
        item1_id = item1.id
        item2_id = item2.id
        item3_id = item3.id
        item4_id = item4.id
        item5_id = item5.id
        print(f"[OK] Seeded items: M1 Items [{item1_id}, {item2_id}, {item3_id}, {item4_id}], M2 Item [{item5_id}]")

    finally:
        db.close()

    # -------------------------------------------------------------
    # TEST 1: List all action items for Member 1
    # -------------------------------------------------------------
    print("\n--- [TEST 1] List all action items ---")
    r1 = client.get("/action-items", headers=h1)
    assert r1.status_code == 200
    items = r1.json()
    assert len(items) == 4, f"Expected 4 items for Member 1, got {len(items)}"
    print(f"[PASS] Test 1: Listed {len(items)} items for Member 1.")

    # -------------------------------------------------------------
    # TEST 2: Filter by status
    # -------------------------------------------------------------
    print("\n--- [TEST 2] Filter by status (?status=in_progress) ---")
    r2 = client.get("/action-items?status=in_progress", headers=h1)
    assert r2.status_code == 200
    items2 = r2.json()
    assert len(items2) == 1
    assert items2[0]["id"] == item1_id
    assert items2[0]["status"] == "in_progress"
    print("[PASS] Test 2: Filtered by status=in_progress correctly.")

    # -------------------------------------------------------------
    # TEST 3: Filter by owner
    # -------------------------------------------------------------
    print("\n--- [TEST 3] Filter by owner (?owner=Priya) ---")
    r3 = client.get("/action-items?owner=Priya", headers=h1)
    assert r3.status_code == 200
    items3 = r3.json()
    assert len(items3) == 2
    assert all(i["owner"] == "Priya" for i in items3)
    print(f"[PASS] Test 3: Filtered by owner=Priya returned {len(items3)} items.")

    # -------------------------------------------------------------
    # TEST 4: Filter by category
    # -------------------------------------------------------------
    print("\n--- [TEST 4] Filter by category (?category=Engineering) ---")
    r4 = client.get("/action-items?category=Engineering", headers=h1)
    assert r4.status_code == 200
    items4 = r4.json()
    assert len(items4) == 1
    assert items4[0]["id"] == item2_id
    print("[PASS] Test 4: Filtered by category=Engineering correctly.")

    # -------------------------------------------------------------
    # TEST 5: Filter clarification items
    # -------------------------------------------------------------
    print("\n--- [TEST 5] Filter clarification items (?needs_clarification=true) ---")
    r5 = client.get("/action-items?needs_clarification=true", headers=h1)
    assert r5.status_code == 200
    items5 = r5.json()
    assert len(items5) == 1
    assert items5[0]["id"] == item2_id
    assert items5[0]["needs_clarification"] is True
    print("[PASS] Test 5: Filtered needs_clarification=true correctly.")

    # -------------------------------------------------------------
    # TEST 6: Filter overdue items
    # -------------------------------------------------------------
    print("\n--- [TEST 6] Filter overdue items (?overdue=true) ---")
    r6 = client.get("/action-items?overdue=true", headers=h1)
    assert r6.status_code == 200
    items6 = r6.json()
    assert len(items6) == 1
    assert items6[0]["id"] == item3_id
    assert items6[0]["deadline"] == yesterday.isoformat()
    assert items6[0]["status"] != "done"
    print("[PASS] Test 6: Filtered overdue=true correctly.")

    # -------------------------------------------------------------
    # TEST 7: PATCH task
    # -------------------------------------------------------------
    print("\n--- [TEST 7] PATCH task title ---")
    r7 = client.patch(f"/action-items/{item1_id}", json={"task": "Write and distribute press release"}, headers=h1)
    assert r7.status_code == 200
    assert r7.json()["task"] == "Write and distribute press release"
    print("[PASS] Test 7: PATCH task title succeeded.")

    # -------------------------------------------------------------
    # TEST 8: PATCH owner/deadline & verify auto-clearing clarification
    # -------------------------------------------------------------
    print("\n--- [TEST 8] PATCH owner & deadline (auto-resolve clarification) ---")
    # item2 initially had owner=None, deadline=None, needs_clarification=True, is_confirmed=False
    r8 = client.patch(f"/action-items/{item2_id}", json={
        "owner": "David",
        "deadline": tomorrow.isoformat()
    }, headers=h1)
    assert r8.status_code == 200
    d8 = r8.json()
    assert d8["owner"] == "David"
    assert d8["deadline"] == tomorrow.isoformat()
    assert d8["needs_clarification"] is False, "Clarification should be auto-cleared when owner & deadline filled"
    assert d8["is_confirmed"] is True, "Item should be auto-confirmed when clarification is resolved"
    print("[PASS] Test 8: PATCH resolved clarification automatically (needs_clarification=False, is_confirmed=True).")

    # -------------------------------------------------------------
    # TEST 9: POST confirm own item
    # -------------------------------------------------------------
    print("\n--- [TEST 9] Member confirming own item ---")
    r9 = client.post(f"/action-items/{item3_id}/confirm", headers=h1)
    assert r9.status_code == 200
    assert r9.json()["is_confirmed"] is True
    assert r9.json()["needs_clarification"] is False
    print("[PASS] Test 9: Member confirmed own item successfully.")

    # -------------------------------------------------------------
    # TEST 10: Member attempting to confirm another user's item -> 403
    # -------------------------------------------------------------
    print("\n--- [TEST 10] Member confirming another user's item (403 Forbidden) ---")
    r10 = client.post(f"/action-items/{item5_id}/confirm", headers=h1)
    print(f"Status: {r10.status_code}")
    assert r10.status_code == 403, f"Expected 403 Forbidden, got {r10.status_code}"
    print("[PASS] Test 10: Unauthorized member confirmation rejected with 403 Forbidden.")

    # -------------------------------------------------------------
    # TEST 11: Admin confirming another user's item -> 200 Allowed
    # -------------------------------------------------------------
    print("\n--- [TEST 11] Admin confirming another user's item (200 Allowed) ---")
    r11 = client.post(f"/action-items/{item5_id}/confirm", headers=h_admin)
    print(f"Status: {r11.status_code}")
    assert r11.status_code == 200
    assert r11.json()["is_confirmed"] is True
    assert r11.json()["needs_clarification"] is False
    print("[PASS] Test 11: Admin permitted to confirm another user's item.")

    # -------------------------------------------------------------
    # TEST 12: Unauthorized request -> 401
    # -------------------------------------------------------------
    print("\n--- [TEST 12] Unauthenticated Request Rejection (401) ---")
    r12 = client.get("/action-items")
    assert r12.status_code == 401
    print("[PASS] Test 12: Unauthenticated request rejected with 401.")

    # -------------------------------------------------------------
    # TEST 13: Cross-user item access -> 404 Not Found
    # -------------------------------------------------------------
    print("\n--- [TEST 13] Member 1 attempting to PATCH Member 2's item ---")
    r13 = client.patch(f"/action-items/{item5_id}", json={"task": "Hacked task"}, headers=h1)
    assert r13.status_code == 404, f"Expected 404, got {r13.status_code}"
    print("[PASS] Test 13: Cross-user modification rejected with 404 Not Found.")

    # -------------------------------------------------------------
    # TEST 14: Successful Merge (Item 4 merged into Item 1)
    # -------------------------------------------------------------
    print("\n--- [TEST 14] Successful Action Item Merge ---")
    r14 = client.post("/action-items/merge", json={
        "primary_id": item1_id,
        "duplicate_id": item4_id
    }, headers=h1)
    assert r14.status_code == 200
    merged = r14.json()
    assert merged["id"] == item1_id
    assert merged["mention_count"] == 2, f"Expected mention_count=2, got {merged['mention_count']}"

    # Verify duplicate is deleted from DB
    db = SessionLocal()
    try:
        dup_check = db.query(ActionItem).filter(ActionItem.id == item4_id).first()
        assert dup_check is None, "Duplicate item should be deleted after merge"
        print("[PASS] Test 14: Merge succeeded, mention_count updated to 2, duplicate item removed.")
    finally:
        db.close()

    # -------------------------------------------------------------
    # TEST 15: Invalid Merge (Self merge & Non-existent item)
    # -------------------------------------------------------------
    print("\n--- [TEST 15] Invalid Merge Rejection (Self-merge & Missing ID) ---")
    r15a = client.post("/action-items/merge", json={"primary_id": item1_id, "duplicate_id": item1_id}, headers=h1)
    assert r15a.status_code == 400
    r15b = client.post("/action-items/merge", json={"primary_id": item1_id, "duplicate_id": 99999}, headers=h1)
    assert r15b.status_code == 404
    print("[PASS] Test 15: Invalid merges rejected with 400/404.")

    # -------------------------------------------------------------
    # TEST 16: Cross-user merge -> Reject (404)
    # -------------------------------------------------------------
    print("\n--- [TEST 16] Cross-User Merge Rejection ---")
    r16 = client.post("/action-items/merge", json={
        "primary_id": item1_id,
        "duplicate_id": item5_id  # belongs to User 2
    }, headers=h1)
    assert r16.status_code == 404
    print("[PASS] Test 16: Cross-user merge rejected with 404.")

    # -------------------------------------------------------------
    # TEST 17: Duplicate Candidate Detection (GET /duplicates/{id})
    # -------------------------------------------------------------
    print("\n--- [TEST 17] Duplicate Candidate Detection (SequenceMatcher > 0.6) ---")
    # Re-insert a fuzzy candidate to test GET /action-items/duplicates/{id}
    db = SessionLocal()
    try:
        candidate_item = ActionItem(
            meeting_id=m1_id, task="Write and distribute tech media press release", owner="Priya",
            deadline=tomorrow, priority="High", category="Marketing", confidence=0.90,
            needs_clarification=False, is_confirmed=True, status="todo", mention_count=1,
            created_at=now, updated_at=now
        )
        db.add(candidate_item)
        db.commit()
        cand_id = candidate_item.id
    finally:
        db.close()


    r17 = client.get(f"/action-items/duplicates/{item1_id}", headers=h1)
    assert r17.status_code == 200
    candidates = r17.json()
    print(f"Candidates found for Item #{item1_id}: {json.dumps(candidates, indent=2)}")
    assert len(candidates) >= 1
    assert candidates[0]["id"] == cand_id
    assert candidates[0]["similarity_score"] > 0.6
    assert candidates[0]["owner"] == "Priya"
    print(f"[PASS] Test 17: Duplicate candidates detected correctly (score: {candidates[0]['similarity_score']}).")

    print("\n==================================================================")
    print("=== ALL 17 STAGE 5A ACTION ITEMS TESTS PASSED ===")
    print("==================================================================")
    return True

if __name__ == "__main__":
    run_stage5a_tests()
