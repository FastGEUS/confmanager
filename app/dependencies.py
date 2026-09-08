import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import decode_access_token
from app.database import get_db
from app.models import Participant

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Participant:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        subject = decode_access_token(token)["sub"]
    except jwt.InvalidTokenError as exc:
        raise unauthorized from exc
    if not isinstance(subject, str) or not subject:
        raise unauthorized
    user = db.scalar(select(Participant).where(func.lower(Participant.email) == subject.lower()))
    if user is None:
        raise unauthorized
    return user


def get_current_committee_user(user: Participant = Depends(get_current_user)) -> Participant:
    if not user.is_committee:
        raise HTTPException(status_code=403, detail="Committee role required")
    return user
