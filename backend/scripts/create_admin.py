"""Create the first administrator account.

Usage:
    uv run python scripts/create_admin.py --email admin@example.com \
        --display-name "Admin" [--password ...]

The password is prompted for when omitted. The account is created verified and
active so it can sign in immediately. Administrators created later through the
admin UI can be managed from there.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

# Running from inside the deployed image means the package is not installed;
# put the application root on the path so `python scripts/create_admin.py`
# works from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session_factory
from app.models.user import UserRole
from app.services import auth_service
from app.services.auth_service import AuthError


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an administrator account")
    parser.add_argument("--email", required=True, help="Administrator email address")
    parser.add_argument("--display-name", required=True, help="Public display name")
    parser.add_argument(
        "--password",
        help="Password (prompted securely when omitted)",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    password = args.password
    if not password:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 1

    async with async_session_factory() as db:
        try:
            user = await auth_service.create_user(
                db,
                email=args.email,
                display_name=args.display_name,
                password=password,
                role=UserRole.ADMIN,
                verified=True,
            )
        except AuthError as exc:
            print(exc.detail, file=sys.stderr)
            return 1

    print(f"Created administrator {user.email} ({user.display_name})")
    return 0


def main() -> int:
    return asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
