from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app import models, schemas
from app.auth import hash_password


def create_participant(db: Session, data: schemas.ParticipantCreate) -> models.Participant:
    existing = db.query(models.Participant).filter(models.Participant.email == data.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    participant = models.Participant(
        full_name=data.full_name,
        email=data.email,
        organization=data.organization,
        hashed_password=hash_password(data.password),
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


def create_application(db: Session, data: schemas.ApplicationCreate) -> models.Application:
    participant = db.query(models.Participant).get(data.participant_id)
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    application = models.Application(participant_id=data.participant_id, topic=data.topic)
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def update_application_status(db: Session, application_id: int, new_status: models.ApplicationStatus) -> models.Application:
    application = db.query(models.Application).get(application_id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    application.status = new_status
    db.commit()
    db.refresh(application)
    return application


def create_fee(db: Session, data: schemas.FeeCreate) -> models.Fee:
    application = db.query(models.Application).get(data.application_id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    existing = db.query(models.Fee).filter(models.Fee.application_id == data.application_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fee already exists for this application")
    fee = models.Fee(application_id=data.application_id, amount=data.amount)
    db.add(fee)
    db.commit()
    db.refresh(fee)
    return fee


def mark_fee_paid(db: Session, fee_id: int) -> models.Fee:
    """Business rule: a fee can be marked as paid only if the related
    application has status ACCEPTED. This is the mandatory domain rule
    required by the LR1 assignment."""
    fee = db.query(models.Fee).get(fee_id)
    if not fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee not found")

    application = db.query(models.Application).get(fee.application_id)
    if application.status != models.ApplicationStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot mark fee as paid: application status is "
                f"'{application.status.value}', expected 'accepted'"
            ),
        )

    fee.status = models.FeeStatus.PAID
    fee.paid_at = datetime.utcnow()
    db.commit()
    db.refresh(fee)
    return fee
