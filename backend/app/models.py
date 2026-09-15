from datetime import datetime, date, timezone
import enum
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, Date, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"

class ItemPriority(str, enum.Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class ItemStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default=UserRole.MEMBER.value, nullable=False)
    confidence_threshold = Column(Float, default=0.75, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    meetings = relationship("Meeting", back_populates="user", cascade="all, delete-orphan")


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(255), nullable=True)
    transcript_text = Column(Text, nullable=False)
    meeting_date = Column(Date, default=date.today, index=True, nullable=False)
    sentiment = Column(String(50), nullable=True)  # "tense" | "smooth" | "neutral"
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="meetings")
    action_items = relationship("ActionItem", back_populates="meeting", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="meeting", cascade="all, delete-orphan")


class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), index=True, nullable=False)
    task = Column(Text, nullable=False)
    owner = Column(String(255), index=True, nullable=True)
    deadline = Column(Date, index=True, nullable=True)
    priority = Column(String(20), index=True, default=ItemPriority.MEDIUM.value, nullable=False)
    category = Column(String(100), index=True, default="General", nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    needs_clarification = Column(Boolean, index=True, default=False, nullable=False)
    is_confirmed = Column(Boolean, index=True, default=False, nullable=False)
    is_duplicate_of = Column(Integer, ForeignKey("action_items.id", ondelete="SET NULL"), index=True, nullable=True)
    source_sentence = Column(Text, nullable=True)
    status = Column(String(20), index=True, default=ItemStatus.TODO.value, nullable=False)
    mention_count = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    meeting = relationship("Meeting", back_populates="action_items")
    clarification_requests = relationship(
        "ClarificationRequest", back_populates="action_item", cascade="all, delete-orphan"
    )
    duplicate_of_item = relationship(
        "ActionItem",
        remote_side=[id],
        backref="duplicates"
    )


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), index=True, nullable=False)
    decision_text = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    meeting = relationship("Meeting", back_populates="decisions")


class ClarificationRequest(Base):
    __tablename__ = "clarification_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    action_item_id = Column(Integer, ForeignKey("action_items.id", ondelete="CASCADE"), index=True, nullable=False)
    question_sent_at = Column(DateTime, default=utc_now, nullable=False)
    answered_at = Column(DateTime, nullable=True)
    reminder_sent_at = Column(DateTime, nullable=True)

    # Relationships
    action_item = relationship("ActionItem", back_populates="clarification_requests")
