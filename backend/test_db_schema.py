import os
import sys
from datetime import datetime, date, timezone

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal, Base
from app.models import User, Meeting, ActionItem, Decision, ClarificationRequest, UserRole, ItemPriority, ItemStatus, utc_now

def test_schema():
    print("=== Stage 1: Testing Database Schema & Models ===")
    
    # Drop and recreate tables for clean test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[OK] Tables created successfully.")

    db = SessionLocal()
    try:
        now = utc_now()
        # 1. Insert User
        user = User(
            email="test.admin@example.com",
            password_hash="$2b$12$eX4mP1eH4sh3dPa55w0rdV41u3F0rT3st1ng0n1y",
            role=UserRole.ADMIN.value,
            confidence_threshold=0.75,
            created_at=now
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[OK] User inserted: ID={user.id}, email={user.email}, role={user.role}, threshold={user.confidence_threshold}")

        # 2. Insert Meeting
        meeting = Meeting(
            user_id=user.id,
            title="Q3 Product Launch Sync",
            transcript_text="Priya: I'll handle the press release by Thursday. Sam: I can take graphics by Wednesday.",
            meeting_date=date.today(),
            sentiment="smooth",
            created_at=now
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        print(f"[OK] Meeting inserted: ID={meeting.id}, title='{meeting.title}', user_id={meeting.user_id}, sentiment={meeting.sentiment}")

        # 3. Insert Action Item
        action_item = ActionItem(
            meeting_id=meeting.id,
            task="Draft and distribute press release",
            owner="Priya",
            deadline=date(2026, 9, 17),
            priority=ItemPriority.HIGH.value,
            category="Marketing",
            confidence=0.95,
            needs_clarification=False,
            is_confirmed=True,
            source_sentence="Priya: I'll handle the press release by Thursday.",
            status=ItemStatus.TODO.value,
            mention_count=1,
            created_at=now,
            updated_at=now
        )
        db.add(action_item)
        db.commit()
        db.refresh(action_item)
        print(f"[OK] ActionItem inserted: ID={action_item.id}, task='{action_item.task}', owner={action_item.owner}, priority={action_item.priority}, confidence={action_item.confidence}")

        # 4. Insert Decision
        decision = Decision(
            meeting_id=meeting.id,
            decision_text="Push enterprise pricing tier discussion to next quarter.",
            context="Enterprise tier requires more enterprise customer research first.",
            created_at=now
        )
        db.add(decision)
        db.commit()
        db.refresh(decision)
        print(f"[OK] Decision inserted: ID={decision.id}, text='{decision.decision_text}'")

        # 5. Insert Clarification Request
        clarification_req = ClarificationRequest(
            action_item_id=action_item.id,
            question_sent_at=now,
            answered_at=None,
            reminder_sent_at=None
        )
        db.add(clarification_req)
        db.commit()
        db.refresh(clarification_req)
        print(f"[OK] ClarificationRequest inserted: ID={clarification_req.id}, item_id={clarification_req.action_item_id}")

        # 6. Verify Relationships & Queries
        retrieved_meeting = db.query(Meeting).filter(Meeting.id == meeting.id).first()
        assert len(retrieved_meeting.action_items) == 1, "Relationship meeting->action_items failed"
        assert len(retrieved_meeting.decisions) == 1, "Relationship meeting->decisions failed"
        assert retrieved_meeting.user.email == "test.admin@example.com", "Relationship meeting->user failed"
        assert len(retrieved_meeting.action_items[0].clarification_requests) == 1, "Relationship action_item->clarification_requests failed"

        print("[OK] All 5 tables verified with foreign key relationships and queries working correctly!")
        return True
    except Exception as e:
        db.rollback()
        print(f"[FAIL] Schema verification failed with error: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    test_schema()
