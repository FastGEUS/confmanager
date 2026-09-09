import os
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["CONFMANAGER_ENV_FILE"] = ""
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = secrets.token_hex(32)

from app.auth import create_access_token, hash_password
from app.database import Base, enable_sqlite_foreign_keys, get_db
from app.main import app
from app.models import Participant

PASSWORD = "test-account-password"


@pytest.fixture(scope="session")
def password_digest():
    return hash_password(PASSWORD)


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture
def db(database):
    with database() as session:
        yield session


@pytest.fixture
def client(database):
    def override_db():
        with database() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def users(db, password_digest):
    first = Participant(
        full_name="First participant",
        email="first@example.com",
        hashed_password=password_digest,
    )
    second = Participant(
        full_name="Second participant",
        email="second@example.com",
        hashed_password=password_digest,
    )
    committee = Participant(
        full_name="Committee",
        email="committee@example.com",
        hashed_password=password_digest,
        is_committee=True,
        role="committee",
    )
    db.add_all([first, second, committee])
    db.commit()
    return first, second, committee


@pytest.fixture
def headers(users):
    return [{"Authorization": "Bearer " + create_access_token(user.email)} for user in users]
