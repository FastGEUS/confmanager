from datetime import datetime
from pydantic import BaseModel, EmailStr

from app.models import ApplicationStatus, FeeStatus


class ParticipantCreate(BaseModel):
    full_name: str
    email: EmailStr
    organization: str | None = None
    password: str


class ParticipantOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    organization: str | None = None
    role: str

    class Config:
        from_attributes = True


class ApplicationCreate(BaseModel):
    participant_id: int
    topic: str


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationOut(BaseModel):
    id: int
    participant_id: int
    topic: str
    status: ApplicationStatus
    submitted_at: datetime

    class Config:
        from_attributes = True


class FeeCreate(BaseModel):
    application_id: int
    amount: float


class FeeOut(BaseModel):
    id: int
    application_id: int
    amount: float
    status: FeeStatus
    paid_at: datetime | None = None

    class Config:
        from_attributes = True
