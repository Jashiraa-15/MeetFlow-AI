import sys
import os
import unittest
from datetime import date, datetime, timedelta

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.config import settings
from app.models import User, Meeting, ActionItem, ClarificationRequest, utc_now
from app.auth import hash_password
from main import app

# Create in-memory SQLite database with StaticPool so all connections share the same memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

class TestN8nWebhookIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)

    def setUp(self):
        self.db = TestingSessionLocal()
        # Clean tables
        self.db.query(ClarificationRequest).delete()
        self.db.query(ActionItem).delete()
        self.db.query(Meeting).delete()
        self.db.query(User).delete()
        self.db.commit()

        # Seed test user
        self.test_user = User(
            email="n8n_test@example.com",
            password_hash=hash_password("password123"),
            role="member",
            confidence_threshold=0.75,
            created_at=utc_now()
        )
        self.db.add(self.test_user)
        self.db.commit()
        self.db.refresh(self.test_user)

    def tearDown(self):
        self.db.close()

    def test_n8n_health_check(self):
        """Verify GET /webhooks/n8n/health returns status ok."""
        resp = client.get("/webhooks/n8n/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "n8n-webhook-bridge")
        self.assertTrue(data["webhook_enabled"])

    def test_webhook_unauthorized_missing_secret(self):
        """Verify rejection when secret is missing."""
        resp = client.post("/webhooks/n8n/clarification", json={
            "action_item_id": 1,
            "owner": "Sam"
        })
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid or missing webhook secret", resp.json()["detail"])

    def test_webhook_unauthorized_invalid_secret(self):
        """Verify rejection when secret is incorrect."""
        resp = client.post(
            "/webhooks/n8n/clarification",
            headers={"X-Webhook-Secret": "wrong-secret-value"},
            json={"action_item_id": 1, "owner": "Sam"}
        )
        self.assertEqual(resp.status_code, 401)

    def test_webhook_not_found_item(self):
        """Verify 404 when action_item_id does not exist."""
        resp = client.post(
            "/webhooks/n8n/clarification",
            headers={"X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET},
            json={"action_item_id": 9999, "owner": "Sam", "deadline": "2026-09-18"}
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("ActionItem #9999 not found", resp.json()["detail"])

    def test_webhook_clarification_resolution(self):
        """Verify full n8n human clarification workflow updates ActionItem and ClarificationRequest."""
        # 1. Create meeting
        meeting = Meeting(
            user_id=self.test_user.id,
            title="Q3 Strategy Review",
            transcript_text="Someone needs to update the pricing page.",
            meeting_date=date.today(),
            created_at=utc_now()
        )
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)

        # 2. Create ambiguous action item with clarification request
        action_item = ActionItem(
            meeting_id=meeting.id,
            task="Update the pricing page",
            owner=None,
            deadline=None,
            priority="Medium",
            category="General",
            confidence=0.45,
            needs_clarification=True,
            is_confirmed=False,
            source_sentence="Someone needs to update the pricing page.",
            created_at=utc_now(),
            updated_at=utc_now()
        )
        self.db.add(action_item)
        self.db.commit()
        self.db.refresh(action_item)

        clar_req = ClarificationRequest(
            action_item_id=action_item.id,
            question_sent_at=utc_now(),
            answered_at=None
        )
        self.db.add(clar_req)
        self.db.commit()

        # 3. Deliver n8n human resolution payload
        resolution_payload = {
            "action_item_id": action_item.id,
            "owner": "Sam",
            "deadline": "2026-09-18",
            "priority": "High",
            "is_confirmed": True,
            "notes": "Clarified via Slack human-in-the-loop"
        }

        resp = client.post(
            "/webhooks/n8n/clarification",
            headers={"X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET},
            json=resolution_payload
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], action_item.id)
        self.assertEqual(data["owner"], "Sam")
        self.assertEqual(data["deadline"], "2026-09-18")
        self.assertEqual(data["priority"], "High")
        self.assertEqual(data["needs_clarification"], False)
        self.assertEqual(data["is_confirmed"], True)

        # 4. Verify DB state directly
        self.db.refresh(action_item)
        self.assertEqual(action_item.owner, "Sam")
        self.assertEqual(action_item.deadline, date(2026, 9, 18))
        self.assertEqual(action_item.priority, "High")
        self.assertFalse(action_item.needs_clarification)
        self.assertTrue(action_item.is_confirmed)

        # 5. Verify ClarificationRequest answered_at was stamped
        self.db.refresh(clar_req)
        self.assertIsNotNone(clar_req.answered_at)

    def test_webhook_with_query_param_secret(self):
        """Verify n8n webhook authentication works with query parameter '?secret='."""
        meeting = Meeting(
            user_id=self.test_user.id,
            title="Sync Meeting",
            transcript_text="Test transcript",
            meeting_date=date.today(),
            created_at=utc_now()
        )
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)

        action_item = ActionItem(
            meeting_id=meeting.id,
            task="Run QA pass",
            owner=None,
            deadline=None,
            priority="Medium",
            category="Engineering",
            confidence=0.4,
            needs_clarification=True,
            is_confirmed=False,
            created_at=utc_now(),
            updated_at=utc_now()
        )
        self.db.add(action_item)
        self.db.commit()
        self.db.refresh(action_item)

        resp = client.post(
            f"/webhooks/n8n/clarification?secret={settings.N8N_WEBHOOK_SECRET}",
            json={
                "action_item_id": action_item.id,
                "owner": "Rahul",
                "deadline": "2026-09-20",
                "is_confirmed": True
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["owner"], "Rahul")
        self.assertFalse(data["needs_clarification"])
        self.assertTrue(data["is_confirmed"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
