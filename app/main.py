from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import Base, engine, get_db
from app.auth import verify_password, create_access_token, decode_access_token
from app.web import router as web_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ConfManager", version="0.1.0")
app.include_router(web_router)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

APP_VERSION = "0.1.0"


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/version")
def version():
    return {"version": APP_VERSION}


def get_current_committee_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    if not payload.get("is_committee"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Committee role required")
    return payload


@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    participant = db.query(models.Participant).filter(models.Participant.email == form_data.username).first()
    if not participant or not verify_password(form_data.password, participant.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token(subject=participant.email, is_committee=participant.is_committee)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/participants", response_model=schemas.ParticipantOut, status_code=status.HTTP_201_CREATED)
def register_participant(data: schemas.ParticipantCreate, db: Session = Depends(get_db)):
    return crud.create_participant(db, data)


@app.get("/participants/{participant_id}", response_model=schemas.ParticipantOut)
def get_participant(participant_id: int, db: Session = Depends(get_db)):
    participant = db.query(models.Participant).get(participant_id)
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    return participant


@app.post("/applications", response_model=schemas.ApplicationOut, status_code=status.HTTP_201_CREATED)
def submit_application(data: schemas.ApplicationCreate, db: Session = Depends(get_db)):
    return crud.create_application(db, data)


@app.get("/applications", response_model=list[schemas.ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    return db.query(models.Application).all()


@app.patch("/applications/{application_id}/status", response_model=schemas.ApplicationOut)
def change_application_status(
    application_id: int,
    data: schemas.ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_committee_user),
):
    return crud.update_application_status(db, application_id, data.status)


@app.post("/fees", response_model=schemas.FeeOut, status_code=status.HTTP_201_CREATED)
def create_fee(
    data: schemas.FeeCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_committee_user),
):
    return crud.create_fee(db, data)


@app.post("/fees/{fee_id}/pay", response_model=schemas.FeeOut)
def pay_fee(
    fee_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_committee_user),
):
    """Marks a fee as paid. Enforces the domain rule: only allowed if the
    related application status is 'accepted'."""
    return crud.mark_fee_paid(db, fee_id)
