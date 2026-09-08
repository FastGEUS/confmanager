from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.auth import hash_password
from app.crud import commit
from app.models import Participant


def create_committee(db: Session, email: str, full_name: str, password: str) -> Participant:
    data = schemas.ParticipantCreate(full_name=full_name, email=email, password=password)
    if db.scalar(select(Participant).where(func.lower(Participant.email) == data.email)):
        raise ValueError("User already exists; bootstrap never promotes an existing account")
    user = Participant(
        full_name=data.full_name,
        email=str(data.email),
        hashed_password=hash_password(data.password),
        role="committee",
        is_committee=True,
    )
    db.add(user)
    commit(db)
    db.refresh(user)
    return user
