import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    # Preserve the initial schema: timestamps are stored as naive UTC values.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ApplicationStatus(str, enum.Enum):
    NEW = "new"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class FeeStatus(str, enum.Enum):
    UNPAID = "unpaid"
    PAID = "paid"


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    organization = Column(String, nullable=True)
    role = Column(String, default="participant")
    hashed_password = Column(String, nullable=False)
    is_committee = Column(Boolean, default=False)

    @property
    def access_role(self):
        return "committee" if self.is_committee else "participant"

    applications = relationship("Application", back_populates="participant")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    topic = Column(String, nullable=False)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.NEW, nullable=False)
    submitted_at = Column(DateTime, default=utc_now)

    participant = relationship("Participant", back_populates="applications")
    fee = relationship("Fee", back_populates="application", uselist=False)


class Fee(Base):
    __tablename__ = "fees"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, unique=True)
    amount = Column(Float, nullable=False)
    status = Column(Enum(FeeStatus), default=FeeStatus.UNPAID, nullable=False)
    paid_at = Column(DateTime, nullable=True)

    application = relationship("Application", back_populates="fee")
