from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# Organization
class OrganizationBase(BaseModel):
    name: str


class OrganizationCreate(OrganizationBase):
    pass


class Organization(OrganizationBase):
    id: int
    whatsapp_number: Optional[str] = None

    class Config:
        orm_mode = True


# User
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str
    organization_name: str  # Create Org during user signup


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class User(UserBase):
    id: int
    organization_id: int
    role: str

    class Config:
        orm_mode = True


# Token
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# Member
class MemberBase(BaseModel):
    name: str
    phone_number: str
    status: Optional[str] = "active"


class MemberCreate(MemberBase):
    pass


class MemberUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    status: Optional[str] = None


class Member(MemberBase):
    id: int
    organization_id: int
    created_at: datetime

    class Config:
        orm_mode = True


# Broadcast
class BroadcastBase(BaseModel):
    content: str
    media_url: Optional[str] = None
    message_type: str = "text"
    template_name: Optional[str] = None
    scheduled_time: Optional[datetime] = None


class BroadcastCreate(BroadcastBase):
    pass


class Broadcast(BroadcastBase):
    id: int
    status: str
    created_at: datetime
    organization_id: int

    class Config:
        orm_mode = True
