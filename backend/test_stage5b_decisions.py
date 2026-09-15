import os
import sys
import json
from datetime import date

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app.models import User, Meeting, Decision, utc_now
from main import app

client = TestClient(app)

def run_stage5b_tests():
    print("==================================================================")
    print("=== Stage 5B: Testing Decisions Endpoint (GET /decisions) ===")
    print("==================================================================")

    # 1. Reset Database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[INIT] Database reset.")

    # 2. Register User 1 and User 2
    r_u1 = client.post("/auth/register", json={"email": "sarah.pm@clarifier.com", "password": "Password123!", "role": "member"})
    token1 = r_u1.json()["access_token"]
    u1_id = r_u1.json()["user"]["id"]
    h1 = {"Authorization": f"Bearer {token1}"}

    r_u2 = client.post("/auth/register", json={"email": "dave.eng@clarifier.com", "password": "Password123!", "role": "member"})
    token2 = r_u2.json()["access_token"]
    u2_id = r_u2.json()["user"]["id"]
    h2 = {"Authorization": f"Bearer {token2}"}

    print(f"[OK] Users created: User 1 ({u1_id}), User 2 ({u2_id})")

    # 3. Seed Meetings and Decisions
    db = SessionLocal()
    now = utc_now()
    try:
        # User 1 - Meeting 1 (Product Launch: 2 decisions from sample transcript)
        m1 = Meeting(user_id=u1_id, title="Product Launch Sync", transcript_text="Transcript 1", meeting_date=date.today(), created_at=now)
        db.add(m1)
        db.flush()
        m1_id = m1.id

        d1 = Decision(
            meeting_id=m1_id,
            decision_text="Push the enterprise pricing tier discussion to next quarter",
            context="Agreed to defer enterprise pricing tier to focus on core release",
            created_at=now
        )
        d2 = Decision(
            meeting_id=m1_id,
            decision_text="Keep the current logo for this launch instead of the redesign",
            context="Branding redesign deferred until Q4",
            created_at=now
        )

        # User 1 - Meeting 2 (Design Sync: 1 decision)
        m2 = Meeting(user_id=u1_id, title="Design Review", transcript_text="Transcript 2", meeting_date=date.today(), created_at=now)
        db.add(m2)
        db.flush()
        m2_id = m2.id

        d3 = Decision(
            meeting_id=m2_id,
            decision_text="Adopt Inter font across all web views",
            context="UI redesign guideline",
            created_at=now
        )

        # User 1 - Meeting 3 (No decisions)
        m3 = Meeting(user_id=u1_id, title="Quick Standup", transcript_text="Quick standup transcript", meeting_date=date.today(), created_at=now)
        db.add(m3)
        db.flush()
        m3_id = m3.id

        # User 2 - Meeting 4 (User 2's Private Meeting: 1 decision)
        m4 = Meeting(user_id=u2_id, title="Backend Architecture", transcript_text="Backend transcript", meeting_date=date.today(), created_at=now)
        db.add(m4)
        db.flush()
        m4_id = m4.id

        d4 = Decision(
            meeting_id=m4_id,
            decision_text="Migrate database storage to PostgreSQL for production",
            context="Architectural choice for enterprise scaling",
            created_at=now
        )

        db.add_all([d1, d2, d3, d4])
        db.commit()
        print(f"[OK] Seeded: U1 Meetings [{m1_id} (2 dec), {m2_id} (1 dec), {m3_id} (0 dec)], U2 Meeting [{m4_id} (1 dec)]")
    finally:
        db.close()

    # -------------------------------------------------------------
    # TEST 1: Authenticated user retrieves all their decisions
    # -------------------------------------------------------------
    print("\n--- [TEST 1] Retrieve all decisions for User 1 ---")
    r1 = client.get("/decisions", headers=h1)
    assert r1.status_code == 200
    decisions_u1 = r1.json()
    print(f"Total decisions returned for User 1: {len(decisions_u1)}")
    assert len(decisions_u1) == 3, f"Expected 3 decisions for User 1, got {len(decisions_u1)}"
    assert all("id" in d and "meeting_id" in d and "decision_text" in d and "context" in d for d in decisions_u1)
    print("[PASS] Test 1: User 1 retrieved all 3 of their decisions.")

    # -------------------------------------------------------------
    # TEST 2: Filter by meeting_id
    # -------------------------------------------------------------
    print("\n--- [TEST 2] Filter decisions by meeting_id ---")
    r2 = client.get(f"/decisions?meeting_id={m1_id}", headers=h1)
    assert r2.status_code == 200
    m1_decisions = r2.json()
    assert len(m1_decisions) == 2, f"Expected 2 decisions for Meeting #{m1_id}, got {len(m1_decisions)}"
    assert all(d["meeting_id"] == m1_id for d in m1_decisions)
    print(f"[PASS] Test 2: Filtered by meeting_id={m1_id} correctly returned 2 decisions.")

    # -------------------------------------------------------------
    # TEST 3: Empty result when meeting has no decisions
    # -------------------------------------------------------------
    print("\n--- [TEST 3] Meeting with no decisions returns empty list ---")
    r3 = client.get(f"/decisions?meeting_id={m3_id}", headers=h1)
    assert r3.status_code == 200
    assert r3.json() == [], "Expected empty list for meeting with 0 decisions"
    print("[PASS] Test 3: Meeting without decisions returned [].")

    # -------------------------------------------------------------
    # TEST 4: Cross-user meeting/decision access is prevented
    # -------------------------------------------------------------
    print("\n--- [TEST 4] Cross-user access prevention ---")
    # User 1 tries to access User 2's meeting decisions
    r4_cross = client.get(f"/decisions?meeting_id={m4_id}", headers=h1)
    print(f"Status for User 1 accessing User 2's meeting: {r4_cross.status_code}")
    assert r4_cross.status_code == 404, f"Expected 404 for cross-user meeting query, got {r4_cross.status_code}"

    # Verify User 1's list never includes User 2's decision
    assert not any("PostgreSQL" in d["decision_text"] for d in decisions_u1)

    # Verify User 2 sees only their 1 decision
    r4_u2 = client.get("/decisions", headers=h2)
    assert r4_u2.status_code == 200
    assert len(r4_u2.json()) == 1
    assert r4_u2.json()[0]["decision_text"] == "Migrate database storage to PostgreSQL for production"
    print("[PASS] Test 4: Cross-user isolation strictly enforced.")

    # -------------------------------------------------------------
    # TEST 5 & 6: Missing and Invalid JWT -> 401
    # -------------------------------------------------------------
    print("\n--- [TEST 5 & 6] Missing and Invalid JWT (401) ---")
    r5 = client.get("/decisions")
    assert r5.status_code == 401, f"Expected 401 for missing token, got {r5.status_code}"

    r6 = client.get("/decisions", headers={"Authorization": "Bearer bad.token.value"})
    assert r6.status_code == 401, f"Expected 401 for invalid token, got {r6.status_code}"
    print("[PASS] Test 5 & 6: Unauthenticated and malformed JWT rejected with 401.")

    # -------------------------------------------------------------
    # TEST 7: Verify returned decisions belong to correct user's meetings
    # -------------------------------------------------------------
    print("\n--- [TEST 7] Database relationship verification ---")
    db = SessionLocal()
    try:
        for d_json in decisions_u1:
            db_meeting = db.query(Meeting).filter(Meeting.id == d_json["meeting_id"]).first()
            assert db_meeting is not None
            assert db_meeting.user_id == u1_id, "Decision belongs to incorrect user!"
        print("[PASS] Test 7: All decisions verified to belong strictly to User 1's meetings in SQLite.")
    finally:
        db.close()

    # -------------------------------------------------------------
    # TEST 8: Verify sample meeting's 2 decisions
    # -------------------------------------------------------------
    print("\n--- [TEST 8] Verify Sample Transcript 2 Decisions ---")
    d_texts = [d["decision_text"] for d in m1_decisions]
    assert any("enterprise pricing" in text.lower() for text in d_texts)
    assert any("current logo" in text.lower() for text in d_texts)
    print(f"Sample Decisions: {json.dumps(d_texts, indent=2)}")
    print("[PASS] Test 8: Sample transcript's 2 decisions retrieved and verified accurately.")

    print("\n==================================================================")
    print("=== ALL 8 STAGE 5B DECISIONS TESTS PASSED ===")
    print("==================================================================")
    return True

if __name__ == "__main__":
    run_stage5b_tests()
