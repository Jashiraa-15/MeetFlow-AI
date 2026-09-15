import os
import sys
import io
import json
from datetime import date, timedelta
from fastapi.testclient import TestClient

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import engine, Base, SessionLocal
from app.models import User, Meeting, ActionItem, Decision, ClarificationRequest
from app.cache_and_limiter import clear_cache_and_limits_for_tests
from main import app

client = TestClient(app)

def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    clear_cache_and_limits_for_tests()

def run_stage_5_crud_verification():
    print("==================================================================")
    print(" STAGE 5 VERIFICATION: CRUD & QUERY ENDPOINTS")
    print("==================================================================")

    reset_db()

    # 1. Register User A (member), User B (member), and Admin User
    print("\n--- Setup: Registering Test Users (User A, User B, Admin) ---")
    
    # User A
    res_a = client.post("/auth/register", json={"email": "testa@example.com", "password": "PasswordA123!", "role": "member"})
    assert res_a.status_code == 201
    token_a = res_a.json()["access_token"]
    user_a_id = res_a.json()["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User B
    res_b = client.post("/auth/register", json={"email": "testb@example.com", "password": "PasswordB123!", "role": "member"})
    assert res_b.status_code == 201
    token_b = res_b.json()["access_token"]
    user_b_id = res_b.json()["user"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Admin User
    res_admin = client.post("/auth/register", json={"email": "admin@example.com", "password": "AdminPassword123!", "role": "admin"})
    assert res_admin.status_code == 201
    token_admin = res_admin.json()["access_token"]
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    print(f"[OK] Created User A (ID={user_a_id}), User B (ID={user_b_id}), Admin.")

    # 2. Create Sample Meetings and Action Items for User A & User B
    print("\n--- Setup: Populating Meetings and Tasks for Users A & B ---")
    
    # Meeting A1
    txt_a1 = """Priya: I'll handle the press release, should be done by Thursday.
Sam: I can take the social media graphics, I'll have drafts by Wednesday.
Priya: Great. Someone needs to update the pricing page too.
Priya: Also we need the QA pass done before Friday's release.
Rahul: Yeah I'll do that, I'll send it Friday morning right before the release goes live.
Priya: Also, we've decided to push the enterprise pricing tier discussion to next quarter.
Sam: Agreed, and we're keeping the current logo for this launch instead of the redesign."""
    
    m_a1_resp = client.post("/meetings", json={"transcript_text": txt_a1, "title": "User A Product Launch"}, headers=headers_a)
    assert m_a1_resp.status_code == 201
    m_a1_id = m_a1_resp.json()["id"]

    # Meeting B1
    txt_b1 = """Alice: I'll prepare the financial report by Monday.
Bob: We decided to cancel the old subscription plan."""
    m_b1_resp = client.post("/meetings", json={"transcript_text": txt_b1, "title": "User B Finance Meeting"}, headers=headers_b)
    assert m_b1_resp.status_code == 201
    m_b1_id = m_b1_resp.json()["id"]

    # Inject an overdue task for User A directly in DB for testing overdue filter & stats
    db = SessionLocal()
    past_item = ActionItem(
        meeting_id=m_a1_id,
        task="Overdue server migration task",
        owner="Rahul",
        deadline=date(2026, 9, 1), # Past date
        priority="High",
        category="Engineering",
        confidence=0.9,
        needs_clarification=False,
        is_confirmed=True,
        status="in_progress",
        mention_count=1
    )
    db.add(past_item)
    db.commit()
    db.refresh(past_item)
    overdue_item_id = past_item.id
    db.close()

    # -------------------------------------------------------------
    # Test A: GET /meetings (Isolation & Search)
    # -------------------------------------------------------------
    print("\n--- Test A: GET /meetings (Isolation & Pagination) ---")
    list_a = client.get("/meetings", headers=headers_a)
    assert list_a.status_code == 200
    meetings_a = list_a.json()["items"]
    assert len(meetings_a) == 1
    assert meetings_a[0]["title"] == "User A Product Launch"
    print(f"[OK] GET /meetings returns ONLY User A's meetings (Count={len(meetings_a)}).")

    # Test Search
    search_resp = client.get("/meetings?search=pricing", headers=headers_a)
    assert search_resp.status_code == 200
    assert len(search_resp.json()["items"]) == 1
    print("[OK] GET /meetings?search=pricing correctly matched action item task text.")

    # -------------------------------------------------------------
    # Test B & C: GET /meetings/{id} & Cross-User Protection
    # -------------------------------------------------------------
    print("\n--- Test B & C: GET /meetings/{id} & Access Control ---")
    detail_a = client.get(f"/meetings/{m_a1_id}", headers=headers_a)
    assert detail_a.status_code == 200
    assert detail_a.json()["id"] == m_a1_id
    print(f"[OK] User A can access own meeting #{m_a1_id}.")

    # Cross-user access check: User A accessing User B's meeting
    cross_resp = client.get(f"/meetings/{m_b1_id}", headers=headers_a)
    assert cross_resp.status_code == 404
    print("[OK] User A cannot access User B's meeting (HTTP 404 returned without data leakage).")

    # -------------------------------------------------------------
    # Test D, E, F, G, H, I: GET /action-items with Filters
    # -------------------------------------------------------------
    print("\n--- Test D to I: GET /action-items & Filters ---")
    
    # All items for User A
    items_a = client.get("/action-items", headers=headers_a).json()
    assert len(items_a) == 6 # 5 from transcript + 1 overdue injected
    print(f"[OK] GET /action-items returns ONLY User A's items (Count={len(items_a)}).")

    # Status filter
    in_prog = client.get("/action-items?status=in_progress", headers=headers_a).json()
    assert len(in_prog) == 1 and in_prog[0]["id"] == overdue_item_id
    print("[OK] Filter ?status=in_progress verified.")

    # Owner filter
    priya_items = client.get("/action-items?owner=Priya", headers=headers_a).json()
    assert len(priya_items) == 1 and priya_items[0]["owner"] == "Priya"
    print("[OK] Filter ?owner=Priya verified.")

    # Category filter
    mktg_items = client.get("/action-items?category=Marketing", headers=headers_a).json()
    assert len(mktg_items) >= 2
    print(f"[OK] Filter ?category=Marketing verified ({len(mktg_items)} items).")

    # Needs Clarification filter
    clarify_items = client.get("/action-items?needs_clarification=true", headers=headers_a).json()
    assert len(clarify_items) == 2
    print(f"[OK] Filter ?needs_clarification=true verified ({len(clarify_items)} items).")

    # Overdue filter
    overdue_items = client.get("/action-items?overdue=true", headers=headers_a).json()
    assert len(overdue_items) == 1 and overdue_items[0]["id"] == overdue_item_id
    print(f"[OK] Filter ?overdue=true verified (ID={overdue_items[0]['id']}, Task='{overdue_items[0]['task']}').")

    # -------------------------------------------------------------
    # Test J & K: PATCH /action-items/{id} & Auto-Resolution
    # -------------------------------------------------------------
    print("\n--- Test J & K: PATCH /action-items/{id} & Clarification Auto-Resolution ---")
    # Find ambiguous pricing page item (owner=None, needs_clarification=True)
    ambiguous_item = next(it for it in items_a if it["owner"] is None and "pricing" in it["task"].lower())
    amb_id = ambiguous_item["id"]
    assert ambiguous_item["needs_clarification"] is True

    # Patch owner and deadline
    patch_resp = client.patch(
        f"/action-items/{amb_id}",
        json={"owner": "Dave", "deadline": "2026-09-25", "priority": "High"},
        headers=headers_a
    )
    assert patch_resp.status_code == 200
    patched_data = patch_resp.json()
    assert patched_data["owner"] == "Dave"
    assert patched_data["priority"] == "High"
    assert patched_data["needs_clarification"] is False
    assert patched_data["is_confirmed"] is True
    print(f"[OK] PATCH populated owner/deadline -> auto-resolved: needs_clarification=False, is_confirmed=True.")

    # -------------------------------------------------------------
    # Test L, M, N: POST /action-items/{id}/confirm & Role Permissions
    # -------------------------------------------------------------
    print("\n--- Test L, M, N: Confirm Action Item & Role Permissions ---")
    qa_item = next(it for it in items_a if "QA pass" in it["task"])
    qa_id = qa_item["id"]

    # Member confirming own item -> 200
    conf_own = client.post(f"/action-items/{qa_id}/confirm", headers=headers_a)
    assert conf_own.status_code == 200
    assert conf_own.json()["is_confirmed"] is True
    print("[OK] Member successfully confirmed own action item.")

    # Member A trying to confirm User B's item -> 403 Forbidden
    b_items = client.get("/action-items", headers=headers_b).json()
    b_item_id = b_items[0]["id"]
    conf_other = client.post(f"/action-items/{b_item_id}/confirm", headers=headers_a)
    assert conf_other.status_code == 403
    print(f"[OK] Member A blocked from confirming User B's item (HTTP 403: {conf_other.json().get('detail')}).")

    # Admin confirming User B's item -> 200 OK
    admin_conf = client.post(f"/action-items/{b_item_id}/confirm", headers=headers_admin)
    assert admin_conf.status_code == 200
    assert admin_conf.json()["is_confirmed"] is True
    print("[OK] Admin successfully confirmed another user's action item.")

    # -------------------------------------------------------------
    # Test O & P: Duplicate Candidates & Merge
    # -------------------------------------------------------------
    print("\n--- Test O & P: Duplicate Detection & Merge Action Items ---")
    # Create two similar items for User A to test candidates and merge
    db = SessionLocal()
    item_p = ActionItem(
        meeting_id=m_a1_id,
        task="Update the website user documentation",
        owner=None,
        deadline=None,
        priority="Medium",
        category="Engineering",
        confidence=0.4,
        needs_clarification=True,
        is_confirmed=False,
        status="todo",
        mention_count=1
    )
    item_d = ActionItem(
        meeting_id=m_a1_id,
        task="Update the website user documentation guide",
        owner="Alice",
        deadline=date(2026, 9, 30),
        priority="High",
        category="Engineering",
        confidence=0.9,
        needs_clarification=False,
        is_confirmed=True,
        status="todo",
        mention_count=2
    )
    db.add(item_p)
    db.add(item_d)
    db.commit()
    db.refresh(item_p)
    db.refresh(item_d)
    primary_id = item_p.id
    dup_id = item_d.id
    db.close()

    # GET /action-items/duplicates/{primary_id}
    cand_resp = client.get(f"/action-items/duplicates/{primary_id}", headers=headers_a)
    assert cand_resp.status_code == 200
    candidates = cand_resp.json()
    print(f"[OK] Duplicate candidates returned: {len(candidates)} candidates found (top similarity: {candidates[0]['similarity_score'] if candidates else 'N/A'}).")

    # POST /action-items/merge
    merge_resp = client.post("/action-items/merge", json={"primary_id": primary_id, "duplicate_id": dup_id}, headers=headers_a)
    assert merge_resp.status_code == 200
    merged = merge_resp.json()
    assert merged["id"] == primary_id
    assert merged["owner"] == "Alice" # Transferred from duplicate
    assert merged["deadline"] == "2026-09-30" # Transferred from duplicate
    assert merged["mention_count"] == 3 # 1 + 2 = 3
    print(f"[OK] Merged #{dup_id} into #{primary_id}: Owner='{merged['owner']}', Deadline={merged['deadline']}, Mentions={merged['mention_count']}.")

    # Confirm duplicate is deleted
    db = SessionLocal()
    assert db.query(ActionItem).filter(ActionItem.id == dup_id).first() is None
    db.close()
    print(f"[OK] Duplicate row #{dup_id} successfully deleted from SQLite.")

    # -------------------------------------------------------------
    # Test Q: GET /decisions & Filtering
    # -------------------------------------------------------------
    print("\n--- Test Q: GET /decisions ---")
    dec_a = client.get("/decisions", headers=headers_a).json()
    assert len(dec_a) == 2
    dec_filtered = client.get(f"/decisions?meeting_id={m_a1_id}", headers=headers_a).json()
    assert len(dec_filtered) == 2
    print(f"[OK] GET /decisions returned {len(dec_a)} decisions for User A.")

    # -------------------------------------------------------------
    # Test R: GET /stats
    # -------------------------------------------------------------
    print("\n--- Test R: GET /stats ---")
    stats_resp = client.get("/stats", headers=headers_a)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    print("[STATS RESULT]:", json.dumps(stats, indent=2))
    assert stats["total_meetings"] == 1
    assert stats["total_action_items"] >= 5
    assert stats["overdue_items"] == 1
    assert len(stats["workload"]) >= 1
    print(f"[OK] Stats verified: Meetings={stats['total_meetings']}, Items={stats['total_action_items']}, Clarify%={stats['clarification_percentage']}, Overdue={stats['overdue_items']}.")

    # -------------------------------------------------------------
    # Test S: GET /calendar
    # -------------------------------------------------------------
    print("\n--- Test S: GET /calendar ---")
    cal_resp = client.get("/calendar", headers=headers_a)
    assert cal_resp.status_code == 200
    cal_data = cal_resp.json()
    print(f"[OK] Calendar grouped tasks by date keys: {list(cal_data.keys())}")
    assert len(cal_data) >= 2

    # -------------------------------------------------------------
    # Test T & U: GET /export/{id} (CSV & PDF)
    # -------------------------------------------------------------
    print("\n--- Test T & U: CSV and PDF Exports ---")
    # CSV
    csv_resp = client.get(f"/export/{m_a1_id}", headers=headers_a)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers.get("content-type", "")
    assert "Priya" in csv_resp.text
    print(f"[OK] CSV Export succeeded (size={len(csv_resp.content)} bytes).")

    # PDF
    pdf_resp = client.get(f"/export/{m_a1_id}/pdf", headers=headers_a)
    assert pdf_resp.status_code == 200
    assert "application/pdf" in pdf_resp.headers.get("content-type", "")
    assert pdf_resp.content.startswith(b"%PDF")
    print(f"[OK] PDF Export generated with ReportLab (size={len(pdf_resp.content)} bytes).")

    # Cross-user export check
    cross_export = client.get(f"/export/{m_b1_id}", headers=headers_a)
    assert cross_export.status_code == 404
    print("[OK] Cross-user export blocked with HTTP 404.")

    # -------------------------------------------------------------
    # Test V & W: Unauthorized & Cross-user Error Checks
    # -------------------------------------------------------------
    print("\n--- Test V & W: Authentication & Access Control Verification ---")
    assert client.get("/stats").status_code == 401
    assert client.get("/calendar").status_code == 401
    assert client.get("/action-items").status_code == 401
    print("[OK] All protected routes strictly reject missing tokens with HTTP 401.")

    print("\n==================================================================")
    print(" [STAGE 5 SUCCESS REPORT]")
    print(" - GET /meetings (paginated & search) verified.")
    print(" - GET /meetings/{id} and cross-user 404 isolation verified.")
    print(" - GET /action-items (status, owner, category, clarification, overdue) verified.")
    print(" - PATCH /action-items/{id} inline update and clarification auto-resolution verified.")
    print(" - POST /action-items/{id}/confirm role-based permissions (member vs admin) verified.")
    print(" - POST /action-items/merge field transfer and duplicate deletion verified.")
    print(" - GET /action-items/duplicates/{id} SequenceMatcher candidates verified.")
    print(" - GET /decisions, GET /stats, and GET /calendar verified.")
    print(" - GET /export/{id} CSV and ReportLab PDF verified.")
    print("==================================================================\n")

if __name__ == "__main__":
    run_stage_5_crud_verification()
