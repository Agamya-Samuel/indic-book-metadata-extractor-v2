"""Create the first administrator from environment variables.

Runs from the backend entrypoint after migrations. Idempotent:

- skips when ``BOOTSTRAP_ADMIN_EMAIL`` or ``BOOTSTRAP_ADMIN_PASSWORD`` is unset
- skips when any administrator already exists (never resets a live deployment)
- skips when the target email is already taken

This replaces the mandatory ``make create-admin`` step on a fresh deploy.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Running from inside the deployed image means the package is not installed;
# put the application root on the path so `python scripts/bootstrap_admin.py`
# works from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.models.user import User, UserRole
from app.services import auth_service
from app.services.auth_service import AuthError


async def _run() -> int:
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip()
    display_name = os.environ.get("BOOTSTRAP_ADMIN_NAME", "").strip() or "Admin"
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")

    if not email or not password:
        print("bootstrap_admin: BOOTSTRAP_ADMIN_EMAIL/PASSWORD not set; skipping.")
        return 0

    async with async_session_factory() as db:
        admin_count = await db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.ADMIN))
        if admin_count:
            print(f"bootstrap_admin: {admin_count} administrator(s) already exist; skipping.")
            return 0

        try:
            user = await auth_service.create_user(
                db,
                email=email,
                display_name=display_name,
                password=password,
                role=UserRole.ADMIN,
                verified=True,
            )
        except AuthError as exc:
            print(f"bootstrap_admin: {exc.detail}; skipping.")
            return 0

    print(f"bootstrap_admin: created administrator {user.email} ({user.display_name})")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
