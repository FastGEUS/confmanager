import os
import secrets
import subprocess
import sys

import pytest

from app.auth import hash_password, verify_password
from app.bootstrap import create_committee
from app.config import Settings
from app.manage import write_local_env


@pytest.mark.parametrize(
    "secret", ["", "short", "dev-secret-change-me", "REPLACE_WITH_GENERATED_SECRET"]
)
def test_missing_or_example_secret_rejected(secret):
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings.from_environ({"SECRET_KEY": secret})


@pytest.mark.parametrize(
    "name,value",
    [
        ("DATABASE_URL", ""),
        ("APP_PORT", "0"),
        ("APP_PORT", "70000"),
        ("APP_PORT", "bad"),
        ("ACCESS_TOKEN_EXPIRE_MINUTES", "0"),
        ("ACCESS_TOKEN_EXPIRE_MINUTES", "2000"),
        ("APP_HOST", ""),
    ],
)
def test_invalid_configuration(name, value):
    with pytest.raises(ValueError):
        Settings.from_environ({"SECRET_KEY": secrets.token_hex(32), name: value})


def test_dotenv_loads_and_real_environment_wins(tmp_path):
    dotenv = tmp_path / "settings.env"
    key = secrets.token_hex(32)
    dotenv.write_text(f"SECRET_KEY={key}\nDATABASE_URL=sqlite:///from-file.db\n")
    env = dict(os.environ)
    env.pop("SECRET_KEY", None)
    env.pop("DATABASE_URL", None)
    env["CONFMANAGER_ENV_FILE"] = str(dotenv)
    command = [
        sys.executable,
        "-c",
        "from app.config import settings; print(settings.database_url)",
    ]
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "sqlite:///from-file.db"
    env["DATABASE_URL"] = "sqlite:///from-process.db"
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "sqlite:///from-process.db"


def test_setup_does_not_overwrite_local_configuration(tmp_path):
    destination = tmp_path / ".env"
    assert write_local_env(destination)
    content = destination.read_text()
    assert "REPLACE_WITH" not in content
    if os.name != "nt":
        assert destination.stat().st_mode & 0o077 == 0
    assert not write_local_env(destination)
    assert destination.read_text() == content


def test_argon2_accepts_long_unicode_password():
    password = "я" * 100
    hashed = hash_password(password)
    assert hashed.startswith("$argon2")
    assert verify_password(password, hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("password", "broken-hash")


def test_bootstrap_and_no_silent_promotion(db, users):
    with pytest.raises(ValueError, match="already exists"):
        create_committee(db, users[0].email, "Committee", "long-test-password")
    assert not users[0].is_committee
    created = create_committee(db, "bootstrap@example.com", "Committee", "long-test-password")
    assert created.is_committee
    assert created.role == "committee"
    assert verify_password("long-test-password", created.hashed_password)


def test_cli_validation_does_not_print_password(tmp_path):
    env = dict(os.environ)
    env["DATABASE_URL"] = "sqlite:///" + str(tmp_path / "bootstrap.db")
    secret_input = "s3cret!!"
    result = subprocess.run(
        [sys.executable, "-m", "app.manage", "create-committee", "--email", "valid@example.com"],
        env=env,
        input=secret_input + "\n" + secret_input + "\n",
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert secret_input not in result.stdout + result.stderr
