"""Block until the configured database accepts connections.

Used by the Docker entrypoint before running migrations: `depends_on: condition: service_healthy` already
waits for PostgreSQL's own health check to pass, but this adds a second, application-level check (it connects
with the exact driver/credentials the app itself will use) so the container never races a database that is
listening but not yet fully initialised.

    python -m app.db.wait_for_db
"""
import sys
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db.database import engine

MAX_ATTEMPTS = 30
DELAY_SECONDS = 2.0


def wait_for_db(max_attempts: int = MAX_ATTEMPTS, delay_seconds: float = DELAY_SECONDS) -> None:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"Database is ready (attempt {attempt}/{max_attempts}).", flush=True)
            return
        except OperationalError as exc:
            last_error = exc
            print(
                f"Database not ready yet (attempt {attempt}/{max_attempts}): "
                f"{str(exc.orig or exc).strip().splitlines()[0]}",
                flush=True,
            )
            time.sleep(delay_seconds)
    print(f"Database did not become ready in time: {last_error}", file=sys.stderr, flush=True)
    sys.exit(1)


if __name__ == "__main__":
    wait_for_db()
