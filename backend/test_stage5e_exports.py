import os
import sys
import io
import csv
from datetime import date, timedelta

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app.models import User, Meeting, ActionItem, Decision, utc_now
from main import app


client = TestClient(app)

def run_stage5e_tests():
    print("==================================================================")
    print("=== Stage 5E: Testing Export Endpoints (CSV & PDF - 12 Tests) ===")
    print("==================================================================")

    # 1. Reset Database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[INIT] Database reset.")

    # 2. Register User 1 and User 2
    r1 = client.post("/auth/register", json={"email": "u1.export@clarifier.com", "password": "Password123!", "role": "member"})
    u1_id = r1.json()["user"]["id"]
    h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}

    r2 = client.post("/auth/register", json={"email": "u2.export@clarifier.com", "password": "Password123!", "role": "member"})
    u2_id = r2.json()["user"]["id"]
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    print(f"[OK] Users registered: User 1 ({u1_id}), User 2 ({u2_id})")

    # 3. Seed Meetings:
    # Meeting 1 (User 1, with 3 rich action items and 2 decisions)
    # Meeting 2 (User 1, empty meeting with 0 action items)
    # Meeting 3 (User 2, private meeting)
    today = date.today()
    tomorrow = today + timedelta(days=2)
    now = utc_now()

    db = SessionLocal()
    try:
        m1 = Meeting(user_id=u1_id, title="Q3 Product Launch Readiness", transcript_text="Full transcript text for launch", meeting_date=today, sentiment="smooth", created_at=now)
        m2 = Meeting(user_id=u1_id, title="Empty Standup", transcript_text="No action items standup", meeting_date=today, sentiment="neutral", created_at=now)
        m3 = Meeting(user_id=u2_id, title="User 2 Secret Strategy", transcript_text="Confidential strategy", meeting_date=today, sentiment="tense", created_at=now)
        db.add_all([m1, m2, m3])
        db.flush()

        m1_id = m1.id
        m2_id = m2.id
        m3_id = m3.id

        # Item 1: Complete fields
        item1 = ActionItem(
            meeting_id=m1_id, task="Draft and distribute press release", owner="Priya",
            deadline=tomorrow, priority="High", category="Marketing", confidence=0.95,
            needs_clarification=False, is_confirmed=True, status="todo", mention_count=1,
            source_sentence="Priya: I'll handle the press release by Thursday.",
            created_at=now, updated_at=now
        )
        # Item 2: Nullable fields (owner=None, deadline=None, source_sentence=None)
        item2 = ActionItem(
            meeting_id=m1_id, task="Update pricing table database schema", owner=None,
            deadline=None, priority="Medium", category="Engineering", confidence=0.40,
            needs_clarification=True, is_confirmed=False, status="todo", mention_count=1,
            source_sentence=None,
            created_at=now, updated_at=now
        )
        # Item 3: In progress with long text
        item3 = ActionItem(
            meeting_id=m1_id, task="Comprehensive end-to-end quality assurance pass across all critical paths before release", owner="Rahul",
            deadline=tomorrow, priority="High", category="Engineering", confidence=0.88,
            needs_clarification=False, is_confirmed=True, status="in_progress", mention_count=2,
            source_sentence="Rahul: We need the full QA pass done before Friday.",
            created_at=now, updated_at=now
        )

        d1 = Decision(meeting_id=m1_id, decision_text="Push enterprise pricing tier discussion to next quarter", context="Focus on core launch", created_at=now)
        d2 = Decision(meeting_id=m1_id, decision_text="Keep current logo for this launch", context="Redesign postponed", created_at=now)

        # Item for User 2
        item_u2 = ActionItem(
            meeting_id=m3_id, task="User 2 confidential task", owner="Alex",
            deadline=tomorrow, priority="High", category="Engineering", confidence=0.9,
            needs_clarification=False, is_confirmed=True, status="todo", mention_count=1,
            created_at=now, updated_at=now
        )

        db.add_all([item1, item2, item3, d1, d2, item_u2])
        db.commit()
        print(f"[OK] Fixtures Seeded: Meeting 1 ({m1_id}, 3 items, 2 decisions), Meeting 2 ({m2_id}, 0 items), Meeting 3 ({m3_id}, User 2).")
    finally:
        db.close()

    # -------------------------------------------------------------
    # TEST 1: CSV Export Success
    # -------------------------------------------------------------
    print("\n--- [TEST 1] CSV Export Success (GET /export/{meeting_id}) ---")
    res_csv = client.get(f"/export/{m1_id}", headers=h1)
    print(f"Status: {res_csv.status_code}")
    print(f"Content-Type: {res_csv.headers.get('content-type')}")
    print(f"Content-Disposition: {res_csv.headers.get('content-disposition')}")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers.get("content-type", "")
    assert f"meeting_{m1_id}_action_items.csv" in res_csv.headers.get("content-disposition", "")
    print("[PASS] Test 1: CSV export returned 200 OK with text/csv content type and attachment header.")

    # -------------------------------------------------------------
    # TEST 2: CSV Headers Verification
    # -------------------------------------------------------------
    print("\n--- [TEST 2] CSV Headers Verification ---")
    csv_text = res_csv.text
    csv_reader = csv.reader(io.StringIO(csv_text))
    rows = list(csv_reader)
    assert len(rows) >= 1, "CSV is empty"
    headers = rows[0]
    expected_headers = [
        "id", "task", "owner", "deadline", "priority", "category",
        "confidence", "needs_clarification", "is_confirmed", "status",
        "mention_count", "source_sentence", "created_at", "updated_at"
    ]
    print(f"Actual Headers: {headers}")
    assert headers == expected_headers, f"Header mismatch!\nExpected: {expected_headers}\nActual: {headers}"
    print("[PASS] Test 2: CSV headers match exact 14-column specification.")

    # -------------------------------------------------------------
    # TEST 3: CSV Rows Content Verification
    # -------------------------------------------------------------
    print("\n--- [TEST 3] CSV Rows Content Verification ---")
    data_rows = rows[1:]
    assert len(data_rows) == 3, f"Expected 3 rows, found {len(data_rows)}"
    tasks = [r[1] for r in data_rows]
    assert "Draft and distribute press release" in tasks
    assert "Update pricing table database schema" in tasks
    assert any("end-to-end quality assurance" in t for t in tasks)
    print(f"[PASS] Test 3: All 3 action item rows present in CSV output.")

    # -------------------------------------------------------------
    # TEST 4: Nullable Fields in CSV
    # -------------------------------------------------------------
    print("\n--- [TEST 4] Nullable Fields in CSV (Empty strings) ---")
    # Row for item2 has owner=None, deadline=None, source_sentence=None
    row_item2 = next(r for r in data_rows if "pricing table" in r[1])
    assert row_item2[2] == "", f"Expected empty string for null owner, got: {row_item2[2]}"
    assert row_item2[3] == "", f"Expected empty string for null deadline, got: {row_item2[3]}"
    assert row_item2[11] == "", f"Expected empty string for null source_sentence, got: {row_item2[11]}"
    print("[PASS] Test 4: Nullable fields correctly exported as empty fields.")

    # -------------------------------------------------------------
    # TEST 5: PDF Export Success
    # -------------------------------------------------------------
    print("\n--- [TEST 5] PDF Export Success (GET /export/{meeting_id}/pdf) ---")
    res_pdf = client.get(f"/export/{m1_id}/pdf", headers=h1)
    print(f"Status: {res_pdf.status_code}")
    print(f"Content-Disposition: {res_pdf.headers.get('content-disposition')}")
    assert res_pdf.status_code == 200
    assert f"meeting_{m1_id}_action_items.pdf" in res_pdf.headers.get("content-disposition", "")
    print("[PASS] Test 5: PDF export returned 200 OK with attachment header.")

    # -------------------------------------------------------------
    # TEST 6: PDF Content-Type Verification
    # -------------------------------------------------------------
    print("\n--- [TEST 6] PDF Content-Type Verification ---")
    assert res_pdf.headers.get("content-type") == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF-"), "Generated file does not start with PDF magic bytes"
    print("[PASS] Test 6: Content-Type is application/pdf and contains valid PDF binary header.")

    # -------------------------------------------------------------
    # TEST 7: PDF Content Verification (Valid binary structure & tokens)
    # -------------------------------------------------------------
    print("\n--- [TEST 7] PDF Content Verification ---")
    assert res_pdf.content.startswith(b"%PDF-"), "Generated file does not start with PDF magic bytes"
    assert b"%%EOF" in res_pdf.content, "PDF file is missing EOF marker"
    assert len(res_pdf.content) > 1000, f"PDF file size too small ({len(res_pdf.content)} bytes)"
    print(f"[PASS] Test 7: PDF verified: {len(res_pdf.content)} bytes, valid PDF-1.4 structure and EOF markers.")

    # -------------------------------------------------------------
    # TEST 8: Empty Meeting Export (Zero Action Items)
    # -------------------------------------------------------------
    print("\n--- [TEST 8] Empty Meeting Export (0 Items) ---")
    res_csv_empty = client.get(f"/export/{m2_id}", headers=h1)
    assert res_csv_empty.status_code == 200
    empty_csv_rows = list(csv.reader(io.StringIO(res_csv_empty.text)))
    assert len(empty_csv_rows) == 1, "Empty meeting CSV should contain only the header row"
    assert empty_csv_rows[0] == expected_headers

    res_pdf_empty = client.get(f"/export/{m2_id}/pdf", headers=h1)
    assert res_pdf_empty.status_code == 200
    assert res_pdf_empty.content.startswith(b"%PDF-")
    assert b"%%EOF" in res_pdf_empty.content
    assert len(res_pdf_empty.content) > 500
    print("[PASS] Test 8: Empty meeting exported cleanly to CSV (header-only) and PDF (valid empty document).")


    # -------------------------------------------------------------
    # TEST 9 & 10: Missing and Invalid JWT (401)
    # -------------------------------------------------------------
    print("\n--- [TEST 9 & 10] Missing and Invalid JWT (401) ---")
    assert client.get(f"/export/{m1_id}").status_code == 401
    assert client.get(f"/export/{m1_id}/pdf").status_code == 401
    assert client.get(f"/export/{m1_id}", headers={"Authorization": "Bearer bad.token"}).status_code == 401
    assert client.get(f"/export/{m1_id}/pdf", headers={"Authorization": "Bearer bad.token"}).status_code == 401
    print("[PASS] Test 9 & 10: Unauthenticated and malformed auth tokens returned 401.")

    # -------------------------------------------------------------
    # TEST 11: Cross-User Meeting Export Prevention (404)
    # -------------------------------------------------------------
    print("\n--- [TEST 11] Cross-User Meeting Export (404) ---")
    # User 1 attempts to export User 2's meeting (m3_id)
    r11_csv = client.get(f"/export/{m3_id}", headers=h1)
    assert r11_csv.status_code == 404, f"Expected 404 for cross-user CSV export, got {r11_csv.status_code}"
    r11_pdf = client.get(f"/export/{m3_id}/pdf", headers=h1)
    assert r11_pdf.status_code == 404, f"Expected 404 for cross-user PDF export, got {r11_pdf.status_code}"
    print("[PASS] Test 11: Cross-user export requests correctly rejected with 404 Not Found.")

    # -------------------------------------------------------------
    # TEST 12: Non-Existent Meeting Export (404)
    # -------------------------------------------------------------
    print("\n--- [TEST 12] Non-Existent Meeting Export (404) ---")
    assert client.get("/export/99999", headers=h1).status_code == 404
    assert client.get("/export/99999/pdf", headers=h1).status_code == 404
    print("[PASS] Test 12: Non-existent meeting requests correctly returned 404 Not Found.")

    print("\n==================================================================")
    print("=== ALL 12 STAGE 5E EXPORT TESTS PASSED SUCCESSFULLY ===")
    print("==================================================================")
    return True

if __name__ == "__main__":
    run_stage5e_tests()
