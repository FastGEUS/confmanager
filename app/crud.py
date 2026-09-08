from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import hash_password


def commit(db: Session):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicting or invalid record") from exc


def create_participant(db: Session, data: schemas.ParticipantCreate) -> models.Participant:
    existing = db.scalar(
        select(models.Participant).where(func.lower(models.Participant.email) == data.email)
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    participant = models.Participant(
        full_name=data.full_name,
        email=str(data.email),
        organization=data.organization,
        hashed_password=hash_password(data.password),
    )
    db.add(participant)
    commit(db)
    db.refresh(participant)
    return participant


def create_application(db: Session, data: schemas.ApplicationCreate) -> models.Application:
    if not db.get(models.Participant, data.participant_id):
        raise HTTPException(status_code=404, detail="Participant not found")
    application = models.Application(participant_id=data.participant_id, topic=data.topic)
    db.add(application)
    commit(db)
    db.refresh(application)
    return application


def locked_application(db: Session, application_id: int) -> models.Application:
    application = db.scalar(
        select(models.Application).where(models.Application.id == application_id).with_for_update()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def update_application_status(db: Session, application_id: int, new_status):
    application = locked_application(db, application_id)
    if (
        application.fee
        and application.fee.status == models.FeeStatus.PAID
        and new_status != models.ApplicationStatus.ACCEPTED
    ):
        raise HTTPException(status_code=400, detail="A paid application must remain accepted")
    application.status = new_status
    commit(db)
    db.refresh(application)
    return application


def create_fee(db: Session, data: schemas.FeeCreate) -> models.Fee:
    application = locked_application(db, data.application_id)
    if application.fee:
        raise HTTPException(status_code=400, detail="Fee already exists for this application")
    fee = models.Fee(application_id=data.application_id, amount=data.amount)
    db.add(fee)
    commit(db)
    db.refresh(fee)
    return fee


def mark_fee_paid(db: Session, fee_id: int) -> models.Fee:
    fee = db.get(models.Fee, fee_id)
    if fee is None:
        raise HTTPException(status_code=404, detail="Fee not found")
    application = locked_application(db, fee.application_id)
    if application.status != models.ApplicationStatus.ACCEPTED:
        raise HTTPException(status_code=400, detail="Only an accepted application can be paid")
    # Lock order is application first, then fee; repeat payment preserves paid_at.
    fee = db.scalar(
        select(models.Fee)
        .where(models.Fee.id == fee_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if fee.status == models.FeeStatus.PAID:
        return fee
    fee.status = models.FeeStatus.PAID
    fee.paid_at = models.utc_now()
    commit(db)
    db.refresh(fee)
    return fee
