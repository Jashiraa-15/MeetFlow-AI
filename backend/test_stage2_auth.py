import os
import sys
import json
from datetime import datetime

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app.models import User, UserRole
from app.auth import verify_password
from main import app

client = TestClient(app)

def run_stage2_tests():
    print("================================================================")
    print("=== Stage 2: Testing Authentication Endpoints in Isolation ===")
    print("================================================================")

    # Re-create database tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[INIT] Fresh database tables initialized.")

    results = {}

    # 1. Test Successful Registration
    print("\n[TEST 1] Successful Registration (member)")
    reg_payload = {
        "email": "sarah.connor@example.com",
        "password": "superSecurePassword123!",
        "role": "member"
    }
    res = client.post("/auth/register", json=reg_payload)
    print(f"Status: {res.status_code}")
    print(f"Response: {res.json()}")
    assert res.status_code == 201, f"Expected 201, got {res.status_code}"
    data = res.json()
    assert "access_token" in data, "Token missing in response"
    assert data["user"]["email"] == "sarah.connor@example.com"
    assert data["user"]["role"] == "member"
    assert data["user"]["confidence_threshold"] == 0.75
    assert "password_hash" not in data["user"], "Security flaw: password_hash leaked in response!"
    member_token = data["access_token"]
    results["1_successful_registration"] = "PASS"
    print("[PASS] Test 1: Successful Registration")

    # 2. Test Duplicate Registration
    print("\n[TEST 2] Duplicate Registration (same email)")
    dup_res = client.post("/auth/register", json=reg_payload)
    print(f"Status: {dup_res.status_code}")
    print(f"Response: {dup_res.json()}")
    assert dup_res.status_code == 400, f"Expected 400, got {dup_res.status_code}"
    assert "already exists" in dup_res.json()["detail"].lower()
    results["2_duplicate_registration"] = "PASS"
    print("[PASS] Test 2: Duplicate Registration correctly rejected (400)")

    # 3. Test Successful Login
    print("\n[TEST 3] Successful Login")
    login_payload = {
        "email": "sarah.connor@example.com",
        "password": "superSecurePassword123!"
    }
    login_res = client.post("/auth/login", json=login_payload)
    print(f"Status: {login_res.status_code}")
    print(f"Response: {login_res.json()}")
    assert login_res.status_code == 200, f"Expected 200, got {login_res.status_code}"
    login_data = login_res.json()
    assert "access_token" in login_data
    assert login_data["user"]["email"] == "sarah.connor@example.com"
    login_token = login_data["access_token"]
    results["3_successful_login"] = "PASS"
    print("[PASS] Test 3: Successful Login")

    # 4. Test Wrong Password
    print("\n[TEST 4] Login with Wrong Password")
    wrong_pwd_payload = {
        "email": "sarah.connor@example.com",
        "password": "wrongPasswordXYZ"
    }
    wrong_pwd_res = client.post("/auth/login", json=wrong_pwd_payload)
    print(f"Status: {wrong_pwd_res.status_code}")
    print(f"Response: {wrong_pwd_res.json()}")
    assert wrong_pwd_res.status_code == 401, f"Expected 401, got {wrong_pwd_res.status_code}"
    results["4_wrong_password"] = "PASS"
    print("[PASS] Test 4: Wrong Password correctly rejected (401)")

    # 5. Test Unknown Email
    print("\n[TEST 5] Login with Unknown Email")
    unknown_email_payload = {
        "email": "nobody@example.com",
        "password": "somePassword123"
    }
    unknown_res = client.post("/auth/login", json=unknown_email_payload)
    print(f"Status: {unknown_res.status_code}")
    print(f"Response: {unknown_res.json()}")
    assert unknown_res.status_code == 401, f"Expected 401, got {unknown_res.status_code}"
    results["5_unknown_email"] = "PASS"
    print("[PASS] Test 5: Unknown Email correctly rejected (401)")

    # 6. Test Missing / Invalid JWT on Protected Endpoint
    print("\n[TEST 6] Missing and Invalid JWT on Protected Endpoint (/auth/me)")
    # No header
    no_auth_res = client.get("/auth/me")
    print(f"No Auth Header Status: {no_auth_res.status_code}, Detail: {no_auth_res.json()}")
    assert no_auth_res.status_code == 401, f"Expected 401, got {no_auth_res.status_code}"
    
    # Invalid JWT
    invalid_auth_res = client.get("/auth/me", headers={"Authorization": "Bearer completely.invalid.token"})
    print(f"Invalid Auth Token Status: {invalid_auth_res.status_code}, Detail: {invalid_auth_res.json()}")
    assert invalid_auth_res.status_code == 401, f"Expected 401, got {invalid_auth_res.status_code}"
    results["6_missing_and_invalid_jwt"] = "PASS"
    print("[PASS] Test 6: Missing and Invalid JWT correctly rejected (401)")

    # 7. Test Valid JWT on Protected Endpoint
    print("\n[TEST 7] Valid JWT against Protected Endpoint (/auth/me)")
    valid_auth_res = client.get("/auth/me", headers={"Authorization": f"Bearer {login_token}"})
    print(f"Status: {valid_auth_res.status_code}")
    print(f"Response: {valid_auth_res.json()}")
    assert valid_auth_res.status_code == 200, f"Expected 200, got {valid_auth_res.status_code}"
    me_data = valid_auth_res.json()
    assert me_data["email"] == "sarah.connor@example.com"
    assert me_data["role"] == "member"
    results["7_valid_jwt_protected_route"] = "PASS"
    print("[PASS] Test 7: Valid JWT accepted on protected endpoint (200)")

    # 8. Test Register Admin User and Verify DB State
    print("\n[TEST 8] Register Admin User & Verify SQLite DB State")
    admin_payload = {
        "email": "admin@clarifier.com",
        "password": "adminMasterPassword999!",
        "role": "admin"
    }
    admin_res = client.post("/auth/register", json=admin_payload)
    assert admin_res.status_code == 201
    assert admin_res.json()["user"]["role"] == "admin"
    
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"Total users in DB: {len(users)}")
        assert len(users) == 2, f"Expected 2 users in DB, found {len(users)}"
        
        sarah = db.query(User).filter(User.email == "sarah.connor@example.com").first()
        assert sarah is not None
        assert sarah.role == "member"
        assert sarah.confidence_threshold == 0.75
        
        admin = db.query(User).filter(User.email == "admin@clarifier.com").first()
        assert admin is not None
        assert admin.role == "admin"
        
        results["8_db_user_verification"] = "PASS"
        print(f"[PASS] Test 8: Verified SQLite DB entries (IDs: {sarah.id}, {admin.id})")

        # 9. Verify Stored Password is Hashed Securely (Bcrypt)
        print("\n[TEST 9] Verify Stored Password Hash Security")
        print(f"Raw Hash in DB for Sarah: {sarah.password_hash}")
        assert sarah.password_hash != "superSecurePassword123!", "CRITICAL: Password is stored in plaintext!"
        assert sarah.password_hash.startswith("$2b$") or sarah.password_hash.startswith("$2a$"), "Password is not a valid bcrypt hash!"
        assert verify_password("superSecurePassword123!", sarah.password_hash) is True
        assert verify_password("wrongPassword", sarah.password_hash) is False
        results["9_password_hash_security"] = "PASS"
        print("[PASS] Test 9: Bcrypt password hashing verified successfully.")
    finally:
        db.close()

    print("\n================================================================")
    print("=== STAGE 2 AUTH TEST SUMMARY: ALL 9 TESTS PASSED ===")
    print("================================================================")
    print(json.dumps(results, indent=2))
    return True

if __name__ == "__main__":
    run_stage2_tests()
