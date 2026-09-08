"""Portable project commands: python -m app.manage <command>."""

import argparse
import os
import secrets

# The verification runner uses fixed argument lists and never executes shell input.
import subprocess  # nosec B404
import sys
from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def write_local_env(destination: Path) -> bool:
    """Create once with private permissions; never overwrite user settings."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as stream:
        stream.write(
            "DATABASE_URL=sqlite:///./confmanager.db\n"
            f"SECRET_KEY={secrets.token_hex(32)}\n"
            "ACCESS_TOKEN_EXPIRE_MINUTES=60\n"
            "APP_HOST=127.0.0.1\n"
            "APP_PORT=8000\n"
        )
    return True


def verify():
    commands = [
        ["pip", "check"],
        ["ruff", "check", "."],
        ["ruff", "format", "--check", "."],
        ["bandit", "-r", "app", "-q"],
        ["pytest", "-q"],
    ]
    for args in commands:
        print(f"Checking: {' '.join(args)}", flush=True)
        # Argument lists are literal module names/options, not user-provided values.
        subprocess.run(  # nosec B603
            [sys.executable, "-m", *args], cwd=ROOT, check=True
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup")
    run = sub.add_parser("run")
    run.add_argument("--reload", action="store_true", help="development only")
    sub.add_parser("init-db")
    sub.add_parser("verify")
    committee = sub.add_parser("create-committee")
    committee.add_argument("--email")
    committee.add_argument("--name", default="Оргкомитет")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == "verify":
        verify()
        return
    if args.command == "setup":
        destination = Path(os.getenv("CONFMANAGER_ENV_FILE") or ROOT / ".env")
        created = write_local_env(destination)
        print("Created local configuration" if created else "Existing configuration preserved")
    if args.command in ("setup", "init-db", "create-committee"):
        from app.database import init_db

        init_db()
    if args.command == "run":
        import uvicorn

        from app.config import settings

        uvicorn.run(
            "app.main:app",
            host=settings.app_host,
            port=settings.app_port,
            reload=args.reload,
        )
    if args.command == "create-committee":
        from pydantic import ValidationError

        from app.bootstrap import create_committee
        from app.database import SessionLocal

        email = args.email or input("Email оргкомитета: ").strip()
        password = getpass("Пароль (12–128 символов): ")
        confirmation = getpass("Повторите пароль: ")
        if password != confirmation:
            raise SystemExit("Пароли не совпадают")
        try:
            with SessionLocal() as db:
                create_committee(db, email, args.name, password)
        except ValidationError as exc:
            # ValidationError.__str__ may include plaintext input; print only messages.
            messages = "; ".join(error["msg"] for error in exc.errors())
            raise SystemExit(messages) from None
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
        print("Учётная запись оргкомитета создана")


if __name__ == "__main__":
    main()
