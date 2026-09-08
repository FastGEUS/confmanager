"""Environment settings; real environment takes precedence over .env."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
env_file = os.getenv("CONFMANAGER_ENV_FILE", str(PROJECT_ROOT / ".env"))
if env_file:
    load_dotenv(env_file, override=False)


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    access_token_expire_minutes: int
    app_host: str
    app_port: int

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        secret = env.get("SECRET_KEY", "")
        forbidden = ("change-me", "replace_with", "dev-secret", "placeholder")
        if len(secret.encode()) < 32 or any(x in secret.lower() for x in forbidden):
            raise ValueError("Set SECRET_KEY to a generated secret of at least 32 bytes")
        database_url = env.get("DATABASE_URL", "sqlite:///./confmanager.db")
        if not database_url.strip():
            raise ValueError("DATABASE_URL must not be empty")
        try:
            expiry = int(env.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
            port = int(env.get("APP_PORT", "8000"))
        except ValueError as exc:
            raise ValueError("Token lifetime and APP_PORT must be integers") from exc
        if not 1 <= expiry <= 1440:
            raise ValueError("Token lifetime must be between 1 and 1440 minutes")
        if not 1 <= port <= 65535:
            raise ValueError("APP_PORT must be between 1 and 65535")
        host = env.get("APP_HOST", "127.0.0.1").strip()
        if not host:
            raise ValueError("APP_HOST must not be empty")
        return cls(database_url, secret, expiry, host, port)


settings = Settings.from_environ()
