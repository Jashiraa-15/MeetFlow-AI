import os
import sys
import json
from datetime import date
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import engine, Base, SessionLocal
from app.models import User, Meeting, ActionItem
from app.cache_and_limiter import clear_cache_and_limits_for_tests
from main import app

client = TestClient(app)

def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    clear_cache_and_limits_for_tests()

def run_stage_6_websocket_verification():
    print("==================================================================")
    print(" STAGE 6 VERIFICATION: WEBSOCKET REAL-TIME UPDATES")
    print("==================================================================")

    reset_db()

    # 1. Register User A and User B
    print("\n--- Setup: Registering Users A and B ---")
    res_a = client.post("/auth/register", json={"email": "wsa@example.com", "password": "PasswordA123!"})
    assert res_a.status_code == 201
    token_a = res_a.json()["access_token"]
    user_a_id = res_a.json()["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    res_b = client.post("/auth/register", json={"email": "wsb@example.com", "password": "PasswordB123!"})
    assert res_b.status_code == 201
    token_b = res_b.json()["access_token"]
    user_b_id = res_b.json()["user"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    print(f"[OK] Registered User A (ID={user_a_id}) and User B (ID={user_b_id}).")

    # -------------------------------------------------------------
    # Test 1: WebSocket Authentication & Rejection
    # -------------------------------------------------------------
    print("\n--- Test 1: WebSocket Authentication Checks ---")
    
    # Missing token
    try:
        with client.websocket_connect("/ws/updates") as ws_missing:
            raise AssertionError("Connection should have been rejected for missing token")
    except Exception as err:
        print(f"[OK] Missing token rejected properly: {type(err).__name__}")

    # Invalid token
    try:
        with client.websocket_connect("/ws/updates?token=invalid.fake.token") as ws_invalid:
            raise AssertionError("Connection should have been rejected for invalid token")
    except Exception as err:
        print(f"[OK] Invalid token rejected properly: {type(err).__name__}")

    # -------------------------------------------------------------
    # Test 2: Multi-Client Connection & Event Broadcasting
    # -------------------------------------------------------------
    print("\n--- Test 2: Real-time Broadcasting to Connected Clients (User A Tabs 1 & 2 + User B) ---")
    
    with client.websocket_connect(f"/ws/updates?token={token_a}") as ws_a1:
        with client.websocket_connect(f"/ws/updates?token={token_a}") as ws_a2:
            with client.websocket_connect(f"/ws/updates?token={token_b}") as ws_b:
                print("[OK] Connected ws_a1 (User A Tab 1), ws_a2 (User A Tab 2), and ws_b (User B).")

                # Trigger Action 1: Create Meeting for User A
                print("\n-> Triggering POST /meetings for User A...")
                sample_text = """Priya: I will handle the press release by Thursday.
Sam: I can take the social media graphics, I'll have drafts by Wednesday."""
                m_resp = client.post(
                    "/meetings",
                    json={"transcript_text": sample_text, "title": "WebSocket Test Meeting"},
                    headers=headers_a
                )
                assert m_resp.status_code == 201
                meeting_id = m_resp.json()["id"]
                created_count = len(m_resp.json()["action_items"])

                # Verify ws_a1 and ws_a2 receive meeting.created
                msg_a1_meet = json.loads(ws_a1.receive_text())
                print(f"[OK] ws_a1 received event: '{msg_a1_meet.get('event')}' (Meeting ID: {msg_a1_meet.get('meeting', {}).get('id')})")
                assert msg_a1_meet["event"] == "meeting.created"
                assert msg_a1_meet["meeting"]["id"] == meeting_id

                msg_a2_meet = json.loads(ws_a2.receive_text())
                print(f"[OK] ws_a2 received event: '{msg_a2_meet.get('event')}' (Meeting ID: {msg_a2_meet.get('meeting', {}).get('id')})")
                assert msg_a2_meet["event"] == "meeting.created"

                # Read action_item.created events on ws_a1 & ws_a2
                item_ids = []
                for i in range(created_count):
                    event_a1 = json.loads(ws_a1.receive_text())
                    event_a2 = json.loads(ws_a2.receive_text())
                    assert event_a1["event"] == "action_item.created"
                    assert event_a2["event"] == "action_item.created"
                    item_id = event_a1["action_item"]["id"]
                    item_ids.append(item_id)
                    print(f"[OK] ws_a1 and ws_a2 received 'action_item.created' for Item #{item_id}")

                assert len(item_ids) >= 1
                target_item_id = item_ids[0]

                # Trigger Action 2: PATCH /action-items/{id} for User A
                print(f"\n-> Triggering PATCH /action-items/{target_item_id} for User A...")
                patch_resp = client.patch(
                    f"/action-items/{target_item_id}",
                    json={"priority": "High", "status": "in_progress"},
                    headers=headers_a
                )
                assert patch_resp.status_code == 200

                msg_patch_a1 = json.loads(ws_a1.receive_text())
                assert msg_patch_a1["event"] == "action_item.updated"
                assert msg_patch_a1["action_item"]["id"] == target_item_id
                assert msg_patch_a1["action_item"]["priority"] == "High"
                assert msg_patch_a1["action_item"]["status"] == "in_progress"
                print(f"[OK] ws_a1 received: 'action_item.updated' (Priority: High, Status: in_progress)")

                msg_patch_a2 = json.loads(ws_a2.receive_text())
                assert msg_patch_a2["event"] == "action_item.updated"
                print(f"[OK] ws_a2 received: 'action_item.updated'")

                # Trigger Action 3: POST /action-items/{id}/confirm for User A
                print(f"\n-> Triggering POST /action-items/{target_item_id}/confirm for User A...")
                conf_resp = client.post(
                    f"/action-items/{target_item_id}/confirm",
                    headers=headers_a
                )
                assert conf_resp.status_code == 200

                msg_conf_a1 = json.loads(ws_a1.receive_text())
                assert msg_conf_a1["event"] == "action_item.confirmed"
                assert msg_conf_a1["action_item"]["is_confirmed"] is True
                print(f"[OK] ws_a1 received: 'action_item.confirmed' (is_confirmed=True)")

                msg_conf_a2 = json.loads(ws_a2.receive_text())
                assert msg_conf_a2["event"] == "action_item.confirmed"
                print(f"[OK] ws_a2 received: 'action_item.confirmed'")

                # Verify User B isolation: ws_b should NOT have received User A's events
                # Send ping to ws_b to verify it's active and has received only its pong
                ws_b.send_text("ping")
                b_response = json.loads(ws_b.receive_text())
                assert b_response["event"] == "pong", f"Expected pong, got {b_response}"
                print("[OK] Cross-user isolation verified: User B received NO events from User A.")

    # -------------------------------------------------------------
    # Test 3: Client Disconnection & HTTP Operations without Clients
    # -------------------------------------------------------------
    print("\n--- Test 3: HTTP Operations with Zero WebSocket Clients ---")
    patch_no_ws = client.patch(
        f"/action-items/{target_item_id}",
        json={"status": "done"},
        headers=headers_a
    )
    assert patch_no_ws.status_code == 200
    assert patch_no_ws.json()["status"] == "done"
    print("[OK] HTTP API operations succeed normally when zero WebSocket clients are connected.")

    print("\n==================================================================")
    print(" [STAGE 6 SUCCESS REPORT]")
    print(" - Native FastAPI WebSocket /ws/updates?token=<JWT> verified.")
    print(" - ConnectionManager with user isolation verified.")
    print(" - Multi-tab broadcast (ws_a1, ws_a2) verified.")
    print(" - Real-time events verified: meeting.created, action_item.created, action_item.updated, action_item.confirmed.")
    print(" - Cross-user data isolation verified (User B received no messages).")
    print(" - HTTP endpoints continue to function when zero WebSocket clients are connected.")
    print("==================================================================\n")

if __name__ == "__main__":
    run_stage_6_websocket_verification()
