from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    Text,
    Enum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class BroadcastStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MemberStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    whatsapp_number = Column(
        String, unique=True, index=True, nullable=True
    )  # The sender number
    whatsapp_business_account_id = Column(String, nullable=True)
    whatsapp_access_token = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="organization")
    members = relationship("Member", back_populates="organization")
    broadcasts = relationship("Broadcast", back_populates="organization")
    subscription = relationship(
        "Subscription", back_populates="organization", uselist=False
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String, nullable=True)
    role = Column(String, default=UserRole.ADMIN)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="users")


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone_number = Column(String, index=True)
    status = Column(String, default=MemberStatus.ACTIVE)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="members")
    broadcast_logs = relationship("BroadcastLog", back_populates="member")


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)  # Message text or caption
    media_url = Column(String, nullable=True)
    message_type = Column(String, default="text")  # text, image, template
    template_name = Column(String, nullable=True)
    status = Column(String, default=BroadcastStatus.DRAFT)
    scheduled_time = Column(DateTime(timezone=True), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="broadcasts")
    logs = relationship("BroadcastLog", back_populates="broadcast")


class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"

    id = Column(Integer, primary_key=True, index=True)
    broadcast_id = Column(Integer, ForeignKey("broadcasts.id"))
    member_id = Column(Integer, ForeignKey("members.id"))
    status = Column(String, default="pending")  # sent, delivered, failed
    error_reason = Column(String, nullable=True)
    message_id = Column(String, nullable=True)  # WhatsApp Message ID
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )

    broadcast = relationship("Broadcast", back_populates="logs")
    member = relationship("Member", back_populates="broadcast_logs")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    plan_type = Column(String, default="standard")
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    organization = relationship("Organization", back_populates="subscription")
