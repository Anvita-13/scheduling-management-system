import logging

from sqlalchemy.exc import OperationalError, ProgrammingError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import DomainError
from app.routers import admin, auth, faculty, notifications, student, timetable

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Centralised scheduling & subject-registration system (Phase 1 DAA algorithms).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.message, "code": exc.code, **exc.extra}
    )


@app.exception_handler(OperationalError)
async def database_unavailable_handler(_: Request, exc: OperationalError):
    # Wrong password / server down / database missing: say so instead of a bare 500.
    logger.error("Database connection problem: %s", str(exc.orig).strip().splitlines()[0] if exc.orig else exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "The server cannot reach the database. Check DATABASE_URL (user, password, host, "
            "database name) in backend/.env and that PostgreSQL is running.",
            "code": "DB_UNAVAILABLE",
        },
    )


@app.exception_handler(ProgrammingError)
async def schema_problem_handler(_: Request, exc: ProgrammingError):
    text = str(exc.orig or exc)
    if "does not exist" in text:  # UndefinedColumn / UndefinedTable: the database has an older structure
        logger.error("Database schema is out of date: %s", text.strip().splitlines()[0])
        return JSONResponse(
            status_code=503,
            content={
                "detail": "The database structure is out of date. Recreate it: run DROP SCHEMA public CASCADE; "
                "CREATE SCHEMA public; then 'alembic upgrade head' and 'python -m app.db.seed' (see SETUP.md).",
                "code": "SCHEMA_OUTDATED",
            },
        )
    raise exc


for r in (auth.router, admin.router, faculty.router, student.router, timetable.router, notifications.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}
