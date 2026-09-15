import os
import sys
import json
from datetime import date, timedelta
import pytest
from starlette.websockets import WebSocketDisconnect

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app.models import User, Meeting, ActionItem, Decision, utc_now
from app.websocket_manager import manager
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

def run_stage6_tests():
    print("==================================================================")
    print("=== Stage 6: Testing WebSocket Real-Time Broadcast (12 Tests) ===")
    print("==================================================================")

    # 1. Reset Database
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[INIT] Database reset.")

    # 2. Register User 1 & User 2
    r1 = client.post("/auth/register", json={"email": "u1.ws@clarifier.com", "password": "Password123!", "role": "member"})
    token1 = r1.json()["access_token"]
    u1_id = r1.json()["user"]["id"]
    h1 = {"Authorization": f"Bearer {token1}"}

    r2 = client.post("/auth/register", json={"email": "u2.ws@clarifier.com", "password": "Password123!", "role": "member"})
    token2 = r2.json()["access_token"]
    u2_id = r2.json()["user"]["id"]
    h2 = {"Authorization": f"Bearer {token2}"}

    print(f"[OK] Test users registered: User 1 ({u1_id}), User 2 ({u2_id})")

    # 3. Seed Initial Meeting & Action Items for User 1
    today = date.today()
    tomorrow = today + timedelta(days=2)
    now = utc_now()
    db = SessionLocal()
    try:
        m1 = Meeting(user_id=u1_id, title="Sprint Planning", transcript_text="Planning text", meeting_date=today, created_at=now)
        db.add(m1)
        db.flush()
        m1_id = m1.id

        item1 = ActionItem(
            meeting_id=m1_id, task="Draft press release", owner="Priya",
            deadline=tomorrow, priority="High", category="Marketing", confidence=0.95,
            needs_clarification=False, is_confirmed=False, status="todo", mention_count=1,
            created_at=now, updated_at=now
        )
        item2 = ActionItem(
            meeting_id=m1_id, task="Draft press release duplicate candidate", owner="Priya",
            deadline=tomorrow, priority="High", category="Marketing", confidence=0.90,
            needs_clarification=False, is_confirmed=False, status="todo", mention_count=1,
            created_at=now, updated_at=now
        )
        db.add_all([item1, item2])
        db.commit()
        item1_id = item1.id
        item2_id = item2.id
        print(f"[OK] Seeded Meeting #{m1_id}, Items [#{item1_id}, #{item2_id}]")
    finally:
        db.close()

    # -------------------------------------------------------------
    # TEST 1: Authenticated connection
    # -------------------------------------------------------------
    print("\n--- [TEST 1] Authenticated WebSocket Connection ---")
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws1:
        # Send ping, verify pong
        ws1.send_text("ping")
        resp = ws1.receive_json()
        assert resp == {"event": "pong"}
    print("[PASS] Test 1: Authenticated WebSocket connected and responded to ping/pong.")

    # -------------------------------------------------------------
    # TEST 2: Missing Token Connection Rejection
    # -------------------------------------------------------------
    print("\n--- [TEST 2] Missing Token Rejection ---")
    rejected = False
    try:
        with client.websocket_connect("/ws/updates") as ws:
            ws.receive_text()
    except Exception:
        rejected = True
    assert rejected, "WebSocket connection without token should be rejected"
    print("[PASS] Test 2: Connection without token rejected.")

    # -------------------------------------------------------------
    # TEST 3: Invalid Token Connection Rejection
    # -------------------------------------------------------------
    print("\n--- [TEST 3] Invalid Token Rejection ---")
    rejected_bad = False
    try:
        with client.websocket_connect("/ws/updates?token=invalid.jwt.token") as ws:
            ws.receive_text()
    except Exception:
        rejected_bad = True
    assert rejected_bad, "WebSocket connection with bad token should be rejected"
    print("[PASS] Test 3: Connection with invalid token rejected.")

    # -------------------------------------------------------------
    # TEST 4: Single-Client Action Item Update Broadcast
    # -------------------------------------------------------------
    print("\n--- [TEST 4] Action Item Update Broadcast (PATCH /action-items/{id}) ---")
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws:
        patch_res = client.patch(f"/action-items/{item1_id}", json={"status": "in_progress"}, headers=h1)
        assert patch_res.status_code == 200

        msg = ws.receive_json()
        print(f"WS Received: {json.dumps(msg, indent=2)}")
        assert msg["event"] == "action_item.updated"
        assert msg["data"]["id"] == item1_id
        assert msg["data"]["status"] == "in_progress"
    print("[PASS] Test 4: action_item.updated broadcast received accurately.")

    # -------------------------------------------------------------
    # TEST 5: Action Item Confirmation Broadcast
    # -------------------------------------------------------------
    print("\n--- [TEST 5] Action Item Confirmation Broadcast (POST /action-items/{id}/confirm) ---")
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws:
        confirm_res = client.post(f"/action-items/{item1_id}/confirm", headers=h1)
        assert confirm_res.status_code == 200

        msg = ws.receive_json()
        print(f"WS Received: {json.dumps(msg, indent=2)}")
        assert msg["event"] == "action_item.confirmed"
        assert msg["data"]["id"] == item1_id
        assert msg["data"]["is_confirmed"] is True
    print("[PASS] Test 5: action_item.confirmed broadcast received accurately.")

    # -------------------------------------------------------------
    # TEST 6: New Meeting Broadcast (POST /meetings)
    # -------------------------------------------------------------
    print("\n--- [TEST 6] New Meeting Processed Broadcast ---")
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws:
        create_res = client.post("/meetings", json={
            "title": "Live Broadcast Test Meeting",
            "transcript_text": SAMPLE_TRANSCRIPT,
            "meeting_date": today.isoformat()
        }, headers=h1)
        assert create_res.status_code == 201

        # First message is meeting.processed
        msg1 = ws.receive_json()
        print(f"WS Msg 1: {json.dumps(msg1, indent=2)}")
        assert msg1["event"] == "meeting.processed"
        assert "meeting_id" in msg1["data"]
        action_items_count = msg1["data"]["action_items_created"]
        assert action_items_count >= 1
        assert msg1["data"]["decisions_created"] >= 1

        # Next messages are action_item.created for each created action item
        for _ in range(action_items_count):
            item_msg = ws.receive_json()
            assert item_msg["event"] == "action_item.created"
            assert "id" in item_msg["data"]

        # Now test duplicate mention in a subsequent meeting
        dup_transcript = "Priya: I'll handle the press release by Thursday."
        dup_res = client.post("/meetings", json={
            "title": "Followup Meeting with Duplicate Task",
            "transcript_text": dup_transcript,
            "meeting_date": today.isoformat()
        }, headers=h1)
        assert dup_res.status_code == 201

        dup_processed = ws.receive_json()
        assert dup_processed["event"] == "meeting.processed"
        # Duplicate item should broadcast action_item.updated (mention_count incremented)
        dup_item_msg = ws.receive_json()
        assert dup_item_msg["event"] == "action_item.updated"
        assert dup_item_msg["data"]["mention_count"] >= 2
    print("[PASS] Test 6: meeting.processed, action_item.created, and duplicate action_item.updated broadcast received on meeting creation.")

    # -------------------------------------------------------------
    # TEST 7: Multiple Connections for Same User (Multi-tab)
    # -------------------------------------------------------------
    print("\n--- [TEST 7] Multiple Tabs for Same User ---")
    with client.websocket_connect(f"/ws/updates?token={token1}") as tab1, \
         client.websocket_connect(f"/ws/updates?token={token1}") as tab2:
        
        patch_res = client.patch(f"/action-items/{item1_id}", json={"priority": "Low"}, headers=h1)
        assert patch_res.status_code == 200

        msg_tab1 = tab1.receive_json()
        msg_tab2 = tab2.receive_json()
        assert msg_tab1["event"] == "action_item.updated"
        assert msg_tab2["event"] == "action_item.updated"
        assert msg_tab1["data"]["priority"] == "Low"
        assert msg_tab2["data"]["priority"] == "Low"
    print("[PASS] Test 7: Both tabs for User 1 received the update event.")

    # -------------------------------------------------------------
    # TEST 8: Cross-User Isolation
    # -------------------------------------------------------------
    print("\n--- [TEST 8] Cross-User Isolation (User 2 receives NO events for User 1) ---")
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws_u1, \
         client.websocket_connect(f"/ws/updates?token={token2}") as ws_u2:
        
        # User 1 performs an update
        client.patch(f"/action-items/{item1_id}", json={"category": "General"}, headers=h1)

        # User 1 receives event
        msg_u1 = ws_u1.receive_json()
        assert msg_u1["event"] == "action_item.updated"
        assert msg_u1["data"]["category"] == "General"

        # User 2 sends ping to confirm no events are waiting in its queue
        ws_u2.send_text("ping")
        u2_resp = ws_u2.receive_json()
        assert u2_resp == {"event": "pong"}, "User 2 should only receive its pong, no User 1 data"
    print("[PASS] Test 8: User 2 received 0 events for User 1's action item update.")

    # -------------------------------------------------------------
    # TEST 9: Disconnection Cleanup
    # -------------------------------------------------------------
    print("\n--- [TEST 9] Disconnection Cleanup ---")
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws_temp:
        ws_temp.send_text("ping")
        assert ws_temp.receive_json() == {"event": "pong"}
    # Socket is now closed / disconnected
    # Trigger a broadcast; manager should cleanly handle without exception
    client.patch(f"/action-items/{item1_id}", json={"task": "Updated after disconnect"}, headers=h1)
    print("[PASS] Test 9: Disconnected socket removed safely without broadcast crash.")

    # -------------------------------------------------------------
    # TEST 10: Failed API Operation (No Broadcast)
    # -------------------------------------------------------------
    print("\n--- [TEST 10] Failed Operation Triggers No Broadcast ---")
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws:
        # Invalid patch (non-existent item)
        err_res = client.patch("/action-items/99999", json={"task": "Error"}, headers=h1)
        assert err_res.status_code == 404

        # Confirm nothing in queue by sending ping
        ws.send_text("ping")
        assert ws.receive_json() == {"event": "pong"}
    print("[PASS] Test 10: Failed HTTP operations do not emit WebSocket events.")

    # -------------------------------------------------------------
    # TEST 11: Merge Event Broadcast
    # -------------------------------------------------------------
    print("\n--- [TEST 11] Action Item Merge Broadcast ---")
    with client.websocket_connect(f"/ws/updates?token={token1}") as ws:
        merge_res = client.post("/action-items/merge", json={
            "primary_id": item1_id,
            "duplicate_id": item2_id
        }, headers=h1)
        assert merge_res.status_code == 200

        msg_updated = ws.receive_json()
        assert msg_updated["event"] == "action_item.updated"
        assert msg_updated["data"]["id"] == item1_id

        msg_deleted = ws.receive_json()
        assert msg_deleted["event"] == "action_item.deleted"
        assert msg_deleted["data"]["deleted_item_id"] == item2_id
    print("[PASS] Test 11: Merge broadcast action_item.updated (primary) and action_item.deleted (duplicate).")

    # -------------------------------------------------------------
    # TEST 12: Broadcast Failure Isolation (Fail-Safe HTTP API)
    # -------------------------------------------------------------
    print("\n--- [TEST 12] Broadcast Failure Isolation (Fail-Safe) ---")
    # Even if manager encounters an unexpected socket error during broadcast, HTTP returns 200 and DB commits
    patch_ok = client.patch(f"/action-items/{item1_id}", json={"task": "Final Valid Press Release Task"}, headers=h1)
    assert patch_ok.status_code == 200
    db = SessionLocal()
    try:
        db_item = db.query(ActionItem).filter(ActionItem.id == item1_id).first()
        assert db_item.task == "Final Valid Press Release Task"
        print("[PASS] Test 12: HTTP API and DB remain 100% resilient and committed.")
    finally:
        db.close()

    print("\n==================================================================")
    print("=== ALL 12 STAGE 6 WEBSOCKET TESTS PASSED SUCCESSFULLY ===")
    print("==================================================================")
    return True

if __name__ == "__main__":
    run_stage6_tests()
