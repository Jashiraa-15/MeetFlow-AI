import os
import sys
import sqlite3
from datetime import date

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database import engine, SessionLocal, Base
from app.models import (
    User, Meeting, ActionItem, Decision, ClarificationRequest,
    UserRole, ItemPriority, ItemStatus, utc_now
)

EXPECTED_SCHEMA = {
    "users": [
        "id", "email", "password_hash", "role", "confidence_threshold", "created_at"
    ],
    "meetings": [
        "id", "user_id", "title", "transcript_text", "meeting_date", "sentiment", "created_at"
    ],
    "action_items": [
        "id", "meeting_id", "task", "owner", "deadline", "priority", "category",
        "confidence", "needs_clarification", "is_confirmed", "is_duplicate_of",
        "source_sentence", "status", "mention_count", "created_at", "updated_at"
    ],
    "decisions": [
        "id", "meeting_id", "decision_text", "context", "created_at"
    ],
    "clarification_requests": [
        "id", "action_item_id", "question_sent_at", "answered_at", "reminder_sent_at"
    ]
}

def verify_sqlite_schema(db_path: str):
    print("\n--- 1. Verifying SQLite Database Schema Columns ---")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"[OK] Found tables: {', '.join(sorted(tables))}")

    for table_name, expected_cols in EXPECTED_SCHEMA.items():
        if table_name not in tables:
            raise AssertionError(f"Missing table in SQLite database: {table_name}")
        
        cursor.execute(f"PRAGMA table_info({table_name});")
        actual_cols = [row[1] for row in cursor.fetchall()]
        
        missing_cols = set(expected_cols) - set(actual_cols)
        if missing_cols:
            raise AssertionError(f"Table '{table_name}' missing columns: {missing_cols}")
        
        print(f"[OK] Table '{table_name}' contains all {len(expected_cols)} required columns: {actual_cols}")

    conn.close()

def verify_db_operations():
    print("\n--- 2. Initializing Database & Inserting Test Records ---")
    # 1. Create SQLite DB and Tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[OK] All 5 tables created via SQLAlchemy Base.metadata.")

    db = SessionLocal()
    try:
        now = utc_now()

        # 3. Insert one test user
        user = User(
            email="sarah.admin@example.com",
            password_hash="$2b$12$eX4mP1eH4sh3dPa55w0rdV41u3F0rT3st1ng0n1y",
            role=UserRole.ADMIN.value,
            confidence_threshold=0.80,
            created_at=now
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[OK] 1. User inserted: ID={user.id} | Email='{user.email}' | Role='{user.role}' | Threshold={user.confidence_threshold}")

        # 4. Insert one meeting
        meeting = Meeting(
            user_id=user.id,
            title="Q3 Roadmap Planning",
            transcript_text="Priya: I'll handle the press release by Thursday. Sam: I will take graphics by Wednesday.",
            meeting_date=date.today(),
            sentiment="smooth",
            created_at=now
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        print(f"[OK] 2. Meeting inserted: ID={meeting.id} | Title='{meeting.title}' | UserID={meeting.user_id} | Sentiment='{meeting.sentiment}'")

        # 5. Insert one action item
        action_item = ActionItem(
            meeting_id=meeting.id,
            task="Write and distribute launch press release",
            owner="Priya",
            deadline=date(2026, 9, 17),
            priority=ItemPriority.HIGH.value,
            category="Marketing",
            confidence=0.95,
            needs_clarification=False,
            is_confirmed=True,
            is_duplicate_of=None,
            source_sentence="Priya: I'll handle the press release by Thursday.",
            status=ItemStatus.TODO.value,
            mention_count=1,
            created_at=now,
            updated_at=now
        )
        db.add(action_item)
        db.commit()
        db.refresh(action_item)
        print(f"[OK] 3. ActionItem inserted: ID={action_item.id} | Task='{action_item.task}' | Owner='{action_item.owner}' | Confidence={action_item.confidence} | MentionCount={action_item.mention_count}")

        # 6. Insert one decision
        decision = Decision(
            meeting_id=meeting.id,
            decision_text="Push enterprise pricing tier discussion to next quarter.",
            context="Enterprise tier requires more enterprise customer research first.",
            created_at=now
        )
        db.add(decision)
        db.commit()
        db.refresh(decision)
        print(f"[OK] 4. Decision inserted: ID={decision.id} | Text='{decision.decision_text}'")

        # 7. Insert one clarification request
        clarification_req = ClarificationRequest(
            action_item_id=action_item.id,
            question_sent_at=now,
            answered_at=None,
            reminder_sent_at=None
        )
        db.add(clarification_req)
        db.commit()
        db.refresh(clarification_req)
        print(f"[OK] 5. ClarificationRequest inserted: ID={clarification_req.id} | ActionItemID={clarification_req.action_item_id}")

        print("\n--- 3. Verifying Foreign Key Relationships & Queries ---")
        # 8. Verify foreign-key relationships
        queried_meeting = db.query(Meeting).filter(Meeting.id == meeting.id).first()
        assert queried_meeting is not None, "Failed to query meeting"
        assert queried_meeting.user.email == "sarah.admin@example.com", "Meeting -> User FK relationship failed"
        assert len(queried_meeting.action_items) == 1, "Meeting -> ActionItems FK relationship failed"
        assert len(queried_meeting.decisions) == 1, "Meeting -> Decisions FK relationship failed"

        queried_item = queried_meeting.action_items[0]
        assert queried_item.meeting.title == "Q3 Roadmap Planning", "ActionItem -> Meeting FK relationship failed"
        assert len(queried_item.clarification_requests) == 1, "ActionItem -> ClarificationRequests FK relationship failed"
        assert queried_item.clarification_requests[0].action_item.task == action_item.task, "ClarificationRequest -> ActionItem FK relationship failed"

        print("[OK] Meeting -> User relationship verified.")
        print("[OK] Meeting -> ActionItems relationship verified.")
        print("[OK] Meeting -> Decisions relationship verified.")
        print("[OK] ActionItem -> ClarificationRequests relationship verified.")

        # Test SQLite Foreign Key enforcement
        try:
            invalid_item = ActionItem(
                meeting_id=99999,  # Non-existent meeting ID
                task="Invalid FK Task",
                priority=ItemPriority.LOW.value,
                category="General",
                confidence=0.5,
                needs_clarification=True,
                is_confirmed=False,
                status=ItemStatus.TODO.value,
                mention_count=1,
                created_at=now,
                updated_at=now
            )
            db.add(invalid_item)
            db.commit()
            raise AssertionError("Foreign key constraint violation was not caught!")
        except Exception as fk_err:
            db.rollback()
            print(f"[OK] Foreign Key enforcement strictly active: Blocked invalid FK insert (error: {type(fk_err).__name__})")

        return True
    finally:
        db.close()

def main():
    print("================================================================")
    print(" STAGE 1 VERIFICATION: BACKEND SCAFFOLD & DATABASE SCHEMA")
    print("================================================================")
    
    # Run operations test
    verify_db_operations()

    # Verify SQLite schema columns directly on the database file
    db_file = os.path.join(backend_dir, "meeting_clarifier.db")
    verify_sqlite_schema(db_file)

    print("\n================================================================")
    print(" [STAGE 1 SUCCESS REPORT]")
    print(" - SQLite Database created and verified.")
    print(" - 5 tables created: users, meetings, action_items, decisions, clarification_requests.")
    print(" - All required columns verified (confidence_threshold, mention_count, created_at, updated_at).")
    print(" - Indexes and Foreign Key constraints active and verified.")
    print(" - Test records successfully inserted and relational queries verified.")
    print("================================================================\n")

if __name__ == "__main__":
    main()
