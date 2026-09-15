import os
import sys
import json
from datetime import date, timedelta
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import Base, engine, SessionLocal
from app.models import User, Meeting, ActionItem, Decision, ClarificationRequest
from main import app

client = TestClient(app)

SAMPLE_TRANSCRIPT = """Priya: Okay so for the launch next week, I'll handle the press release, should be done by Thursday.
Sam: I can take the social media graphics, I'll have drafts by Wednesday.
Priya: Great. Someone needs to update the pricing page too, but I'm not sure who's free for that.
Rahul: I could maybe look at it if no one else can, but I have the client call all week.
Priya: Let's flag that one. Also we need the QA pass done before Friday's release.
Sam: I think that's on the QA team but honestly I don't know who exactly picks that up.
Priya: Okay, let's note that as unclear too. Last thing - can someone send the launch email to the mailing list?
Rahul: Yeah I'll do that, I'll send it Friday morning right before the release goes live.
Priya: Also, we've decided to push the enterprise pricing tier discussion to next quarter.
Sam: Agreed, and we're keeping the current logo for this launch instead of the redesign."""

def run_stage8_e2e_tests():
    print("==================================================================")
    print("=== Stage 8: Full End-to-End Integration & Frontend Verification ===")
    print("==================================================================")

    # 1. Reset Database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[INIT] Fresh SQLite database initialized.")

    # -------------------------------------------------------------
    # STEP 1 & 2: User Registration & Login
    # -------------------------------------------------------------
    print("\n--- [STEP 1 & 2] User Registration & Login ---")
    reg_u1 = client.post("/auth/register", json={
        "email": "user1.e2e@clarifier.com",
        "password": "Password123!",
        "role": "member"
    })
    assert reg_u1.status_code == 201, f"Registration failed: {reg_u1.text}"
    token_u1 = reg_u1.json()["access_token"]
    u1_id = reg_u1.json()["user"]["id"]
    h1 = {"Authorization": f"Bearer {token_u1}"}

    # Register User 2 for Cross-User Isolation checks
    reg_u2 = client.post("/auth/register", json={
        "email": "user2.e2e@clarifier.com",
        "password": "Password123!",
        "role": "member"
    })
    assert reg_u2.status_code == 201
    token_u2 = reg_u2.json()["access_token"]
    u2_id = reg_u2.json()["user"]["id"]
    h2 = {"Authorization": f"Bearer {token_u2}"}

    # Verify Login
    login_u1 = client.post("/auth/login", json={
        "email": "user1.e2e@clarifier.com",
        "password": "Password123!"
    })
    assert login_u1.status_code == 200
    assert "access_token" in login_u1.json()
    print(f"[PASS] Steps 1-3: Registered and Authenticated User 1 ({u1_id}) & User 2 ({u2_id}).")

    # -------------------------------------------------------------
    # STEP 3: Connect WebSocket for Live Sync
    # -------------------------------------------------------------
    print("\n--- [STEP 3] Establish Authenticated WebSocket Stream ---")
    with client.websocket_connect(f"/ws/updates?token={token_u1}") as ws1, \
         client.websocket_connect(f"/ws/updates?token={token_u2}") as ws2:

        # -------------------------------------------------------------
        # STEP 4: Submit Sample Meeting Transcript
        # -------------------------------------------------------------
        print("\n--- [STEP 4] Submit Meeting Transcript (POST /meetings) ---")
        today_str = date.today().isoformat()
        meeting_resp = client.post("/meetings", json={
            "title": "Q3 Launch Readiness Sync",
            "transcript_text": SAMPLE_TRANSCRIPT,
            "meeting_date": today_str
        }, headers=h1)
        assert meeting_resp.status_code == 201
        m_data = meeting_resp.json()
        meeting_id = m_data["id"]
        print(f"[OK] Created Meeting #{meeting_id}: '{m_data['title']}' | Sentiment: {m_data['sentiment']}")

        # -------------------------------------------------------------
        # STEP 5 & 6: Verify Extracted Action Items & Decisions
        # -------------------------------------------------------------
        print("\n--- [STEP 5 & 6] Verify Action Items & Decisions in DB ---")
        items_resp = client.get(f"/action-items", headers=h1)
        assert items_resp.status_code == 200
        action_items = items_resp.json()
        assert len(action_items) >= 4
        print(f"[OK] Found {len(action_items)} extracted action items for User 1.")

        decisions_resp = client.get(f"/decisions?meeting_id={meeting_id}", headers=h1)
        assert decisions_resp.status_code == 200
        decisions = decisions_resp.json()
        assert len(decisions) >= 2
        print(f"[OK] Found {len(decisions)} extracted decisions for Meeting #{meeting_id}.")

        # -------------------------------------------------------------
        # STEP 7: Verify Clarification Queue Items
        # -------------------------------------------------------------
        print("\n--- [STEP 7] Verify Clarification Queue (needs_clarification=true) ---")
        clar_resp = client.get("/action-items?needs_clarification=true", headers=h1)
        assert clar_resp.status_code == 200
        clar_items = clar_resp.json()
        assert len(clar_items) >= 1
        unclear_item = clar_items[0]
        print(f"[OK] Clarification Queue contains {len(clar_items)} items. Target item: #{unclear_item['id']} ('{unclear_item['task']}')")

        # -------------------------------------------------------------
        # STEP 8: Verify Real-Time WebSocket Events on Creation
        # -------------------------------------------------------------
        print("\n--- [STEP 8] Verify WebSocket Live Stream Delivery ---")
        msg_proc = ws1.receive_json()
        assert msg_proc["event"] == "meeting.processed"
        assert msg_proc["data"]["meeting_id"] == meeting_id

        # Drain created action items
        for _ in range(msg_proc["data"]["action_items_created"]):
            ai_msg = ws1.receive_json()
            assert ai_msg["event"] == "action_item.created"
        print("[PASS] Step 8: meeting.processed and action_item.created events received on User 1 stream.")

        # User 2 should have received zero events
        ws2.send_text("ping")
        assert ws2.receive_json() == {"event": "pong"}
        print("[PASS] User 2 stream received 0 User 1 events (User Isolation verified).")

        # -------------------------------------------------------------
        # STEP 9: Verify Stats Endpoint
        # -------------------------------------------------------------
        print("\n--- [STEP 9] Verify Stats Computation (GET /stats) ---")
        stats_resp = client.get("/stats", headers=h1)
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats["total_meetings"] == 1
        assert stats["total_action_items"] == len(action_items)
        assert stats["clarification_percentage"] > 0
        print(f"[PASS] Step 9: Stats verified: {json.dumps(stats, indent=2)}")

        # -------------------------------------------------------------
        # STEP 10: Verify Calendar Endpoint
        # -------------------------------------------------------------
        print("\n--- [STEP 10] Verify Calendar Grouping (GET /calendar) ---")
        cal_resp = client.get("/calendar", headers=h1)
        assert cal_resp.status_code == 200
        calendar_data = cal_resp.json()
        assert isinstance(calendar_data, dict)
        print(f"[PASS] Step 10: Calendar returned dates: {list(calendar_data.keys())}")

        # -------------------------------------------------------------
        # STEP 11: Verify Export Endpoints (CSV & PDF)
        # -------------------------------------------------------------
        print("\n--- [STEP 11] Verify Export Downloads (CSV & PDF) ---")
        csv_resp = client.get(f"/export/{meeting_id}", headers=h1)
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        assert len(csv_resp.content) > 50

        pdf_resp = client.get(f"/export/{meeting_id}/pdf", headers=h1)
        assert pdf_resp.status_code == 200
        assert "application/pdf" in pdf_resp.headers["content-type"]
        assert len(pdf_resp.content) > 500
        print("[PASS] Step 11: Both CSV and PDF downloads generated valid binary payloads.")

        # -------------------------------------------------------------
        # STEP 12 & 13: Patch Action Item & Receive WS Event
        # -------------------------------------------------------------
        print("\n--- [STEP 12 & 13] PATCH Action Item & Verify Real-Time Sync ---")
        patch_resp = client.patch(f"/action-items/{unclear_item['id']}", json={
            "owner": "Priya",
            "deadline": (date.today() + timedelta(days=3)).isoformat(),
            "status": "in_progress"
        }, headers=h1)
        assert patch_resp.status_code == 200

        ws_patch = ws1.receive_json()
        assert ws_patch["event"] == "action_item.updated"
        assert ws_patch["data"]["id"] == unclear_item["id"]
        assert ws_patch["data"]["owner"] == "Priya"
        print(f"[PASS] Steps 12-13: Action item patched and action_item.updated broadcasted.")

        # -------------------------------------------------------------
        # STEP 14 & 15: Confirm Action Item & Receive WS Event
        # -------------------------------------------------------------
        print("\n--- [STEP 14 & 15] Confirm Action Item (POST /confirm) & Verify WS ---")
        confirm_resp = client.post(f"/action-items/{unclear_item['id']}/confirm", headers=h1)
        assert confirm_resp.status_code == 200

        ws_conf = ws1.receive_json()
        assert ws_conf["event"] == "action_item.confirmed"
        assert ws_conf["data"]["id"] == unclear_item["id"]
        print(f"[PASS] Steps 14-15: Action item confirmed and action_item.confirmed broadcasted.")

        # -------------------------------------------------------------
        # STEP 16: Multi-Tenant Data Isolation Checks
        # -------------------------------------------------------------
        print("\n--- [STEP 16] Multi-Tenant Data Isolation Checks ---")
        u2_meetings = client.get("/meetings", headers=h2).json()
        assert len(u2_meetings["items"]) == 0

        u2_items = client.get("/action-items", headers=h2).json()
        assert len(u2_items) == 0

        u2_decisions = client.get(f"/decisions?meeting_id={meeting_id}", headers=h2)
        assert u2_decisions.status_code == 404

        u2_export = client.get(f"/export/{meeting_id}", headers=h2)
        assert u2_export.status_code == 404
        print("[PASS] Step 16: Strict isolation verified. User 2 cannot access any User 1 data.")

        # -------------------------------------------------------------
        # STEP 17: Unauthenticated & Malformed Token Protection
        # -------------------------------------------------------------
        print("\n--- [STEP 17] Unauthenticated & Protected Routes ---")
        assert client.get("/action-items").status_code == 401
        assert client.get("/stats").status_code == 401
        assert client.get("/calendar").status_code == 401
        assert client.get("/auth/me").status_code == 401
        print("[PASS] Step 17: Unauthenticated access safely rejected with 401.")

    print("\n==================================================================")
    print("=== ALL 17 END-TO-END INTEGRATION FLOWS PASSED SUCCESSFULLY ===")
    print("==================================================================")
    return True

if __name__ == "__main__":
    run_stage8_e2e_tests()
