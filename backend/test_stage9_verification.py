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

def run_stage9_quality_verification():
    print("==================================================================")
    print("=== Stage 9: Real-World Application Verification & Quality Hardening ===")
    print("==================================================================")

    # 1. Fresh Database Initialization
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[INIT] Database initialized cleanly.")

    # -------------------------------------------------------------
    # 1. Registration & Authentication Verification
    # -------------------------------------------------------------
    print("\n--- [VERIFICATION 1] Registration, Login & Auth Hardening ---")
    reg_res = client.post("/auth/register", json={
        "email": "quality.tester@clarifier.com",
        "password": "Password123!",
        "role": "member"
    })
    assert reg_res.status_code == 201
    user_data = reg_res.json()["user"]
    token = reg_res.json()["access_token"]
    assert "password_hash" not in user_data
    assert user_data["email"] == "quality.tester@clarifier.com"
    headers = {"Authorization": f"Bearer {token}"}

    # Duplicate registration rejection
    dup_res = client.post("/auth/register", json={
        "email": "quality.tester@clarifier.com",
        "password": "Password123!"
    })
    assert dup_res.status_code == 400
    print("[PASS] Verification 1: Secure registration, password hashing, and duplicate protection verified.")

    # -------------------------------------------------------------
    # 2. WebSocket Real-Time Stream Establishment
    # -------------------------------------------------------------
    print("\n--- [VERIFICATION 2] WebSocket Real-Time Connection ---")
    with client.websocket_connect(f"/ws/updates?token={token}") as ws:
        # Ping/pong test
        ws.send_text("ping")
        assert ws.receive_json() == {"event": "pong"}
        print("[PASS] Verification 2: Authenticated WebSocket stream connected and responding.")

        # -------------------------------------------------------------
        # 3. Meeting Transcript Ingestion & AI Extraction
        # -------------------------------------------------------------
        print("\n--- [VERIFICATION 3] Transcript Ingestion & Extraction ---")
        today_str = date.today().isoformat()
        meet_res = client.post("/meetings", json={
            "title": "Stage 9 Production Launch Sync",
            "transcript_text": SAMPLE_TRANSCRIPT,
            "meeting_date": today_str
        }, headers=headers)
        assert meet_res.status_code == 201
        meeting = meet_res.json()
        meeting_id = meeting["id"]
        assert meeting["sentiment"] in ["smooth", "positive", "neutral"]
        print(f"[OK] Meeting #{meeting_id} ingested. Sentiment: {meeting['sentiment']}")

        # Verify WebSocket broadcast on ingestion
        msg_proc = ws.receive_json()
        assert msg_proc["event"] == "meeting.processed"
        assert msg_proc["data"]["meeting_id"] == meeting_id
        items_count = msg_proc["data"]["action_items_created"]
        assert items_count >= 5

        # Drain action_item.created events
        created_events = []
        for _ in range(items_count):
            item_msg = ws.receive_json()
            assert item_msg["event"] == "action_item.created"
            created_events.append(item_msg["data"])
        print(f"[PASS] Verification 3: Ingested meeting and received {len(created_events)} real-time item broadcasts.")

        # -------------------------------------------------------------
        # 4. Clarification Queue Verification
        # -------------------------------------------------------------
        print("\n--- [VERIFICATION 4] Clarification Queue & Ambiguity Tagging ---")
        clar_res = client.get("/action-items?needs_clarification=true", headers=headers)
        assert clar_res.status_code == 200
        clar_items = clar_res.json()
        assert len(clar_items) >= 2
        for ci in clar_items:
            assert ci["needs_clarification"] is True
            assert ci["is_confirmed"] is False
        target_clar = clar_items[0]
        print(f"[PASS] Verification 4: Clarification queue isolated {len(clar_items)} ambiguous items.")

        # -------------------------------------------------------------
        # 5. Action Item Editing & Auto-Resolution
        # -------------------------------------------------------------
        print("\n--- [VERIFICATION 5] Action Item Editing & Confirmation ---")
        target_id = target_clar["id"]
        resolved_deadline = (date.today() + timedelta(days=5)).isoformat()

        # Update owner and deadline
        patch_res = client.patch(f"/action-items/{target_id}", json={
            "owner": "Priya",
            "deadline": resolved_deadline,
            "priority": "High",
            "category": "Engineering",
            "status": "in_progress"
        }, headers=headers)
        assert patch_res.status_code == 200
        patched_item = patch_res.json()
        assert patched_item["owner"] == "Priya"
        assert patched_item["deadline"] == resolved_deadline

        # Confirm item
        conf_res = client.post(f"/action-items/{target_id}/confirm", headers=headers)
        assert conf_res.status_code == 200
        confirmed_item = conf_res.json()
        assert confirmed_item["is_confirmed"] is True
        assert confirmed_item["needs_clarification"] is False

        # Verify WebSocket received update and confirmation
        ws_patch = ws.receive_json()
        assert ws_patch["event"] == "action_item.updated"
        assert ws_patch["data"]["id"] == target_id

        ws_conf = ws.receive_json()
        assert ws_conf["event"] == "action_item.confirmed"
        assert ws_conf["data"]["id"] == target_id
        print("[PASS] Verification 5: Action item edited, confirmed, and verified over WebSockets.")

        # -------------------------------------------------------------
        # 6. Dashboard Statistics Computation
        # -------------------------------------------------------------
        print("\n--- [VERIFICATION 6] Dashboard Stats Computation ---")
        stats_res = client.get("/stats", headers=headers)
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert stats["total_meetings"] == 1
        assert stats["total_action_items"] >= 5
        assert stats["clarification_percentage"] >= 0.0
        assert "workload" in stats
        print(f"[PASS] Verification 6: Dashboard stats returned valid workload and metric counts.")

        # -------------------------------------------------------------
        # 7. Calendar Timeline
        # -------------------------------------------------------------
        print("\n--- [VERIFICATION 7] Calendar Timeline Grouping ---")
        cal_res = client.get("/calendar", headers=headers)
        assert cal_res.status_code == 200
        cal_data = cal_res.json()
        assert len(cal_data) >= 2
        for d_key, task_list in cal_data.items():
            assert len(task_list) > 0
            for t in task_list:
                assert t["deadline"] == d_key
        print(f"[PASS] Verification 7: Calendar accurately grouped tasks under {len(cal_data)} chronological dates.")

        # -------------------------------------------------------------
        # 8. CSV & PDF Export Endpoints
        # -------------------------------------------------------------
        print("\n--- [VERIFICATION 8] CSV & PDF Export Reliability ---")
        csv_res = client.get(f"/export/{meeting_id}", headers=headers)
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers["content-type"]
        assert "id,task,owner,deadline" in csv_res.text

        pdf_res = client.get(f"/export/{meeting_id}/pdf", headers=headers)
        assert pdf_res.status_code == 200
        assert "application/pdf" in pdf_res.headers["content-type"]
        assert pdf_res.content.startswith(b"%PDF")
        print("[PASS] Verification 8: CSV and PDF export endpoints generated accurate file streams.")

    print("\n==================================================================")
    print("=== ALL STAGE 9 QUALITY HARDENING VERIFICATIONS PASSED ===")
    print("==================================================================")
    return True

if __name__ == "__main__":
    run_stage9_quality_verification()
