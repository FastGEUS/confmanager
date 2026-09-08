import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app import APP_VERSION, crud, models, schemas
from app.auth import create_access_token, verify_and_upgrade_password
from app.database import get_db, init_db
from app.dependencies import get_current_committee_user, get_current_user
from app.web import APP_ROOT
from app.web import router as web_router

logger = logging.getLogger(__name__)
BEARER_SCHEME = "bearer"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ConfManager", version=APP_VERSION, lifespan=lifespan)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "static")), name="static")


@app.exception_handler(SQLAlchemyError)
async def database_error(_request: Request, exc: SQLAlchemyError):
    logger.error("Database operation failed: %s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})


@app.get("/health")
def health():
    return {"status": "ok", "time": models.utc_now().isoformat()}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc
    return {"status": "ready"}


@app.get("/version")
def version():
    return {"version": APP_VERSION}


@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    participant = db.scalar(
        select(models.Participant).where(
            func.lower(models.Participant.email) == form_data.username.strip().lower()
        )
    )
    valid, upgraded = (
        verify_and_upgrade_password(form_data.password, participant.hashed_password)
        if participant
        else (False, None)
    )
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if upgraded:
        participant.hashed_password = upgraded
        crud.commit(db)
    return {"access_token": create_access_token(participant.email), "token_type": BEARER_SCHEME}


@app.get("/auth/me", response_model=schemas.ParticipantOut)
def current_user(user: models.Participant = Depends(get_current_user)):
    return user


@app.post("/participants", response_model=schemas.ParticipantOut, status_code=201)
def register_participant(data: schemas.ParticipantCreate, db: Session = Depends(get_db)):
    return crud.create_participant(db, data)


@app.get("/participants/{participant_id}", response_model=schemas.ParticipantOut)
def get_participant(
    participant_id: int,
    user: models.Participant = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if participant_id != user.id and not user.is_committee:
        raise HTTPException(status_code=403, detail="Access to another participant is forbidden")
    participant = db.get(models.Participant, participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    return participant


@app.post("/applications", response_model=schemas.ApplicationOut, status_code=201)
def submit_application(
    data: schemas.ApplicationCreate,
    user: models.Participant = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    participant_id = data.participant_id if data.participant_id is not None else user.id
    if participant_id != user.id and not user.is_committee:
        raise HTTPException(status_code=403, detail="Cannot submit for another participant")
    return crud.create_application(db, data.model_copy(update={"participant_id": participant_id}))


@app.get("/applications", response_model=list[schemas.ApplicationOut])
def list_applications(
    user: models.Participant = Depends(get_current_user), db: Session = Depends(get_db)
):
    query = select(models.Application).options(selectinload(models.Application.fee))
    if not user.is_committee:
        query = query.where(models.Application.participant_id == user.id)
    return db.scalars(query.order_by(models.Application.id)).all()


@app.patch("/applications/{application_id}/status", response_model=schemas.ApplicationOut)
def change_application_status(
    application_id: int,
    data: schemas.ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    _user: models.Participant = Depends(get_current_committee_user),
):
    return crud.update_application_status(db, application_id, data.status)


@app.post("/fees", response_model=schemas.FeeOut, status_code=201)
def create_fee(
    data: schemas.FeeCreate,
    db: Session = Depends(get_db),
    _user: models.Participant = Depends(get_current_committee_user),
):
    return crud.create_fee(db, data)


@app.post("/fees/{fee_id}/pay", response_model=schemas.FeeOut)
def pay_fee(
    fee_id: int,
    db: Session = Depends(get_db),
    _user: models.Participant = Depends(get_current_committee_user),
):
    return crud.mark_fee_paid(db, fee_id)
