import os
import sys
import sqlite3
from fastapi.testclient import TestClient

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import engine, Base, SessionLocal
from app.models import User
from app.config import settings
from main import app

client = TestClient(app)

def reset_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def verify_stage_2_auth():
    print("================================================================")
    print(" STAGE 2 VERIFICATION: AUTHENTICATION (REGISTER + LOGIN + JWT)")
    print("================================================================")
    
    reset_test_db()

    test_email = "test@example.com"
    test_password = "TestPassword123!"

    # -------------------------------------------------------------
    # Test A: Register New User
    # -------------------------------------------------------------
    print("\n--- Test A: User Registration (POST /auth/register) ---")
    reg_response = client.post(
        "/auth/register",
        json={"email": test_email, "password": test_password}
    )
    print(f"Status Code: {reg_response.status_code}")
    assert reg_response.status_code == 201, f"Expected 201 Created, got {reg_response.status_code}: {reg_response.text}"
    
    reg_data = reg_response.json()
    assert "access_token" in reg_data, "Response missing access_token"
    assert reg_data.get("token_type") == "bearer", "Token type must be bearer"
    assert reg_data["user"]["email"] == test_email, "User email mismatch"
    assert reg_data["user"]["role"] == "member", "Default role should be member"
    assert reg_data["user"]["confidence_threshold"] == 0.75, "Default confidence threshold should be 0.75"
    
    token_a = reg_data["access_token"]
    print(f"[OK] Registration successful. Returned JWT (len={len(token_a)}): {token_a[:25]}...")

    # Verify SQLite DB directly for password hashing
    db = SessionLocal()
    try:
        user_in_db = db.query(User).filter(User.email == test_email).first()
        assert user_in_db is not None, "User record not found in database"
        assert user_in_db.password_hash.startswith("$2b$") or user_in_db.password_hash.startswith("$2a$"), "Password is not a valid bcrypt hash"
        assert user_in_db.password_hash != test_password, "Plaintext password detected in database!"
        print(f"[OK] Verified SQLite record: ID={user_in_db.id}, Email='{user_in_db.email}', Role='{user_in_db.role}'")
        print(f"[OK] Password stored as bcrypt hash: '{user_in_db.password_hash[:15]}...' (never plaintext)")
    finally:
        db.close()

    # -------------------------------------------------------------
    # Test B: Duplicate Registration
    # -------------------------------------------------------------
    print("\n--- Test B: Duplicate Registration Check ---")
    dup_response = client.post(
        "/auth/register",
        json={"email": test_email, "password": "DifferentPassword456!"}
    )
    print(f"Status Code: {dup_response.status_code}")
    assert dup_response.status_code in (400, 409), f"Expected 400 or 409 for duplicate registration, got {dup_response.status_code}"
    print(f"[OK] Duplicate registration rejected with HTTP {dup_response.status_code}: {dup_response.json().get('detail')}")

    # Verify total user count remains 1
    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        assert total_users == 1, f"Expected 1 user in DB, found {total_users}"
        print(f"[OK] Total user count in SQLite remains exactly {total_users}")
    finally:
        db.close()

    # -------------------------------------------------------------
    # Test C: Valid Login (POST /auth/login)
    # -------------------------------------------------------------
    print("\n--- Test C: Valid Login (POST /auth/login) ---")
    login_response = client.post(
        "/auth/login",
        json={"email": test_email, "password": test_password}
    )
    print(f"Status Code: {login_response.status_code}")
    assert login_response.status_code == 200, f"Expected 200 OK, got {login_response.status_code}: {login_response.text}"
    
    login_data = login_response.json()
    assert "access_token" in login_data, "Response missing access_token"
    assert login_data["user"]["email"] == test_email, "User email mismatch"
    token_c = login_data["access_token"]
    print(f"[OK] Login successful. Returned JWT (len={len(token_c)}): {token_c[:25]}...")

    # -------------------------------------------------------------
    # Test D: Invalid Login (Wrong Password & Non-existent Email)
    # -------------------------------------------------------------
    print("\n--- Test D: Invalid Login Credentials ---")
    bad_pwd_resp = client.post(
        "/auth/login",
        json={"email": test_email, "password": "IncorrectPassword999!"}
    )
    print(f"Wrong Password Status Code: {bad_pwd_resp.status_code}")
    assert bad_pwd_resp.status_code == 401, f"Expected 401 Unauthorized, got {bad_pwd_resp.status_code}"
    print(f"[OK] Incorrect password correctly rejected with HTTP 401: {bad_pwd_resp.json().get('detail')}")

    bad_user_resp = client.post(
        "/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123!"}
    )
    print(f"Non-existent User Status Code: {bad_user_resp.status_code}")
    assert bad_user_resp.status_code == 401, f"Expected 401 Unauthorized, got {bad_user_resp.status_code}"
    print(f"[OK] Non-existent user correctly rejected with HTTP 401: {bad_user_resp.json().get('detail')}")

    # -------------------------------------------------------------
    # Test E: Protected Route JWT Validation (GET /auth/me)
    # -------------------------------------------------------------
    print("\n--- Test E: Protected Route & JWT Dependency Validation (GET /auth/me) ---")
    
    # 1. Valid Token
    valid_auth_resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token_c}"}
    )
    print(f"Valid Token Status Code: {valid_auth_resp.status_code}")
    assert valid_auth_resp.status_code == 200, f"Expected 200 OK, got {valid_auth_resp.status_code}"
    profile = valid_auth_resp.json()
    assert profile["email"] == test_email, "Profile email mismatch"
    print(f"[OK] Valid JWT accepted. Authenticated User: ID={profile['id']}, Email={profile['email']}, Role={profile['role']}")

    # 2. Missing Token
    missing_auth_resp = client.get("/auth/me")
    print(f"Missing Token Status Code: {missing_auth_resp.status_code}")
    assert missing_auth_resp.status_code == 401, f"Expected 401 Unauthorized, got {missing_auth_resp.status_code}"
    print(f"[OK] Missing token rejected with HTTP 401: {missing_auth_resp.json().get('detail')}")

    # 3. Invalid/Malformed Token
    invalid_auth_resp = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token.string"}
    )
    print(f"Invalid Token Status Code: {invalid_auth_resp.status_code}")
    assert invalid_auth_resp.status_code == 401, f"Expected 401 Unauthorized, got {invalid_auth_resp.status_code}"
    print(f"[OK] Invalid/tampered JWT rejected with HTTP 401: {invalid_auth_resp.json().get('detail')}")

    # -------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------
    print("\n================================================================")
    print(" [STAGE 2 SUCCESS REPORT]")
    print(" - POST /auth/register: User registration and bcrypt password hashing verified.")
    print(" - Duplicate registration blocked with HTTP 400.")
    print(" - POST /auth/login: Valid login returns signed JWT.")
    print(" - Invalid login rejected with HTTP 401.")
    print(" - get_current_user dependency: Valid JWT accepted; missing/invalid tokens return 401.")
    print(" - SQLite Database verification: Password is stored as bcrypt hash ($2b$), never plaintext.")
    print("================================================================\n")

if __name__ == "__main__":
    verify_stage_2_auth()
