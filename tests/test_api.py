from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pytest
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import FeeStatus

PASSWORD = "test-account-password"


def application(client, headers, topic="DevOps доклад"):
    response = client.post("/applications", headers=headers, json={"topic": topic})
    assert response.status_code == 201, response.text
    return response.json()


def test_registration_and_login(client, db):
    response = client.post(
        "/participants",
        json={
            "full_name": "  Иван Иванов  ",
            "email": "IVAN@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    assert response.json()["full_name"] == "Иван Иванов"
    assert response.json()["email"] == "ivan@example.com"
    assert "hashed_password" not in response.json()
    login = client.post("/auth/login", data={"username": "IVAN@example.com", "password": PASSWORD})
    assert login.status_code == 200
    who = client.get(
        "/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}
    )
    assert who.json()["role"] == "participant"


@pytest.mark.parametrize(
    "field,value",
    [
        ("full_name", ""),
        ("full_name", "   "),
        ("full_name", "x" * 201),
        ("email", "broken"),
        ("password", ""),
        ("password", "short"),
        ("password", " " * 12),
        ("password", "x" * 129),
        ("is_committee", True),
    ],
)
def test_invalid_registration(client, field, value):
    data = {"full_name": "Test", "email": "valid@example.com", "password": PASSWORD}
    data[field] = value
    assert client.post("/participants", json=data).status_code == 422


def test_duplicate_email_case_insensitive(client, users):
    response = client.post(
        "/participants",
        json={
            "full_name": "Another",
            "email": "FIRST@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 400


def test_wrong_password(client, users):
    assert (
        client.post(
            "/auth/login",
            data={
                "username": users[0].email,
                "password": "wrong-password",
            },
        ).status_code
        == 401
    )


def test_bcrypt_login_upgrades_without_losing_account(client, db, users):
    old = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    users[0].hashed_password = old
    db.commit()
    response = client.post("/auth/login", data={"username": users[0].email, "password": PASSWORD})
    assert response.status_code == 200
    db.refresh(users[0])
    assert users[0].hashed_password.startswith("$argon2")
    assert users[0].id == 1


def test_no_token(client):
    for method, url, data in [
        ("get", "/applications", None),
        ("get", "/participants/1", None),
        ("post", "/applications", {"topic": "Test"}),
        ("post", "/fees", {"application_id": 1, "amount": 100}),
    ]:
        response = getattr(client, method)(url, **({"json": data} if data else {}))
        assert response.status_code == 401


def test_own_application_and_privacy(client, users, headers):
    first = application(client, headers[0])
    second = application(client, headers[1], "Another talk")
    assert first["participant_id"] == users[0].id
    assert [item["id"] for item in client.get("/applications", headers=headers[0]).json()] == [
        first["id"]
    ]
    assert len(client.get("/applications", headers=headers[2]).json()) == 2
    assert client.get(f"/participants/{users[1].id}", headers=headers[0]).status_code == 403
    assert (
        client.post(
            "/applications",
            headers=headers[0],
            json={
                "participant_id": users[1].id,
                "topic": "Forged authorship",
            },
        ).status_code
        == 403
    )
    assert second["participant_id"] == users[1].id


@pytest.mark.parametrize("topic", ["", "   ", "x" * 501])
def test_invalid_application_topic(client, headers, topic):
    assert (
        client.post("/applications", headers=headers[0], json={"topic": topic}).status_code == 422
    )


def test_committee_submission_for_missing_user(client, headers):
    assert (
        client.post(
            "/applications",
            headers=headers[2],
            json={
                "participant_id": 999,
                "topic": "Test",
            },
        ).status_code
        == 404
    )


def test_full_payment_scenario(client, headers, db):
    item = application(client, headers[0])
    payload = {"application_id": item["id"], "amount": 3000.25}
    assert client.post("/fees", headers=headers[0], json=payload).status_code == 403
    fee = client.post("/fees", headers=headers[2], json=payload)
    assert fee.status_code == 201
    fee_id = fee.json()["id"]
    assert client.post(f"/fees/{fee_id}/pay", headers=headers[2]).status_code == 400
    assert (
        client.patch(
            f"/applications/{item['id']}/status", headers=headers[2], json={"status": "accepted"}
        ).status_code
        == 200
    )
    paid = client.post(f"/fees/{fee_id}/pay", headers=headers[2])
    assert paid.status_code == 200
    assert paid.json()["status"] == FeeStatus.PAID
    repeated = client.post(f"/fees/{fee_id}/pay", headers=headers[2])
    assert repeated.json()["paid_at"] == paid.json()["paid_at"]
    assert (
        client.patch(
            f"/applications/{item['id']}/status", headers=headers[2], json={"status": "rejected"}
        ).status_code
        == 400
    )
    listed = client.get("/applications", headers=headers[0]).json()[0]
    assert listed["fee"]["status"] == "paid"


@pytest.mark.parametrize("status", ["new", "under_review", "rejected"])
def test_payment_rule_all_unaccepted_statuses(client, headers, status):
    item = application(client, headers[0])
    client.patch(f"/applications/{item['id']}/status", headers=headers[2], json={"status": status})
    fee = client.post(
        "/fees",
        headers=headers[2],
        json={
            "application_id": item["id"],
            "amount": 100,
        },
    ).json()
    assert client.post(f"/fees/{fee['id']}/pay", headers=headers[2]).status_code == 400


@pytest.mark.parametrize("amount", [-1, 0, 0.001, 1.234, 10000000000])
def test_invalid_fee_amount(client, headers, amount):
    item = application(client, headers[0])
    assert (
        client.post(
            "/fees",
            headers=headers[2],
            json={
                "application_id": item["id"],
                "amount": amount,
            },
        ).status_code
        == 422
    )


def test_unknown_and_duplicate_records(client, headers):
    item = application(client, headers[0])
    payload = {"application_id": item["id"], "amount": 10}
    assert client.post("/fees", headers=headers[2], json=payload).status_code == 201
    assert client.post("/fees", headers=headers[2], json=payload).status_code == 400
    assert (
        client.post(
            "/fees", headers=headers[2], json={"application_id": 999, "amount": 10}
        ).status_code
        == 404
    )
    assert client.post("/fees/999/pay", headers=headers[2]).status_code == 404
    assert (
        client.patch(
            "/applications/999/status", headers=headers[2], json={"status": "accepted"}
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/applications/{item['id']}/status", headers=headers[2], json={"status": "garbage"}
        ).status_code
        == 422
    )


def test_jwt_claim_cannot_grant_committee_role(client, users):
    token = jwt.encode(
        {
            "sub": users[0].email,
            "is_committee": True,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    assert (
        client.post(
            "/fees",
            headers={"Authorization": "Bearer " + token},
            json={"application_id": 1, "amount": 10},
        ).status_code
        == 403
    )


@pytest.mark.parametrize("kind", ["missing-user", "expired", "wrong-key", "missing-exp"])
def test_invalid_tokens(client, users, kind):
    claims = {"sub": users[0].email, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    secret = settings.secret_key
    if kind == "missing-user":
        claims["sub"] = "missing@example.com"
    elif kind == "expired":
        claims["exp"] = datetime.now(timezone.utc) - timedelta(minutes=5)
    elif kind == "wrong-key":
        secret = "unrelated-key-" * 4
    else:
        del claims["exp"]
    token = jwt.encode(claims, secret, algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_revoked_committee_role_applies_to_existing_token(client, db, users, headers):
    users[2].is_committee = False
    db.commit()
    assert client.get("/auth/me", headers=headers[2]).json()["role"] == "participant"
    assert (
        client.post(
            "/fees", headers=headers[2], json={"application_id": 1, "amount": 10}
        ).status_code
        == 403
    )


def test_deleted_account_invalidates_existing_token(client, db, users, headers):
    db.delete(users[0])
    db.commit()
    assert client.get("/auth/me", headers=headers[0]).status_code == 401


def test_health_readiness_version_and_ui(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json()["status"] == "ready"
    assert client.get("/version").json()["version"] == "0.1.0"
    page = client.get("/")
    assert page.status_code == 200
    for name in ["login-form", "registration-form", "application-form"]:
        assert name in page.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_database_failure_is_reported_without_secret(client):
    class BrokenSession:
        def execute(self, _statement):
            raise OperationalError("test", {}, RuntimeError("sensitive connection information"))

    def broken():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken
    assert client.get("/health").status_code == 200
    response = client.get("/ready")
    assert response.status_code == 503
    assert "sensitive" not in response.text
