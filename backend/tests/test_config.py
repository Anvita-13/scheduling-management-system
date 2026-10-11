from pathlib import Path

import pytest

from app.core.config import Settings


ROOT_ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"

# Same shape as the root .env.example: Compose-only keys (POSTGRES_*, FRONTEND_PORT) and inline comments
# must be tolerated by Settings, and a comma-separated CORS_ORIGINS must parse.
EMBEDDED_ENV_EXAMPLE = """\
POSTGRES_USER=postgres
POSTGRES_PORT=5432            # host port for direct DB access
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/scheduling
SECRET_KEY=local-dev-insecure-secret-change-me-0123456789abcdef
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
FRONTEND_PORT=3000              # the port you open in your browser
"""


def _load_settings_from_dotenv(tmp_path, monkeypatch, text):
    (tmp_path / ".env").write_text(text)
    monkeypatch.chdir(tmp_path)
    for var in ("CORS_ORIGINS", "DATABASE_URL", "SECRET_KEY"):
        monkeypatch.delenv(var, raising=False)
    return Settings()


def test_env_file_in_example_format_loads_as_is(tmp_path, monkeypatch):
    """A `.env` copied from .env.example must produce valid settings (regression: CORS_ORIGINS)."""
    s = _load_settings_from_dotenv(tmp_path, monkeypatch, EMBEDDED_ENV_EXAMPLE)
    assert s.CORS_ORIGINS == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert s.DATABASE_URL.startswith("postgresql+psycopg2://")


@pytest.mark.skipif(not ROOT_ENV_EXAMPLE.exists(), reason="root .env.example is not inside the backend image")
def test_root_env_example_loads_as_is(tmp_path, monkeypatch):
    text = ROOT_ENV_EXAMPLE.read_text()
    if "DATABASE_URL" not in text:  # Compose builds DATABASE_URL itself from POSTGRES_*; supply it as Compose would
        text += "\nDATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/scheduling\n"
    s = _load_settings_from_dotenv(tmp_path, monkeypatch, text)
    assert s.CORS_ORIGINS == ["http://localhost:3000", "http://127.0.0.1:3000"]


@pytest.mark.parametrize("given, expected", [
    ("postgres://u:p@h:5432/d", "postgresql+psycopg2://u:p@h:5432/d"),
    ("postgresql://u:p@h/d?sslmode=require", "postgresql+psycopg2://u:p@h/d?sslmode=require"),
    ("postgresql+psycopg2://u:p@h/d", "postgresql+psycopg2://u:p@h/d"),
    ("sqlite:///./x.db", "sqlite:///./x.db"),
])
def test_database_url_is_normalised_for_hosting_providers(monkeypatch, given, expected):
    monkeypatch.setenv("DATABASE_URL", given)
    assert Settings().DATABASE_URL == expected


def test_database_connection_failure_returns_clear_503(client):
    from sqlalchemy.exc import OperationalError

    from app.db.database import get_db
    from app.main import app

    def broken_db():
        raise OperationalError("connect", {}, Exception('FATAL: password authentication failed for user "postgres"'))
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = broken_db
    r = client.post("/api/auth/login", json={"email": "a@b.edu", "password": "x"})
    assert r.status_code == 503 and r.json()["code"] == "DB_UNAVAILABLE"
    # users get a plain message; technical details (passwords, settings) are never sent to the browser
    assert "try again" in r.json()["detail"] and "DATABASE_URL" not in r.json()["detail"] and "password" not in r.json()["detail"]


def test_cors_origins_accepts_comma_list_json_and_single(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert Settings().CORS_ORIGINS == ["https://a.example", "https://b.example"]
    monkeypatch.setenv("CORS_ORIGINS", '["https://c.example"]')
    assert Settings().CORS_ORIGINS == ["https://c.example"]
    monkeypatch.setenv("CORS_ORIGINS", "https://only.example")
    assert Settings().CORS_ORIGINS == ["https://only.example"]


def test_outdated_database_schema_returns_clear_503(client):
    from sqlalchemy.exc import ProgrammingError

    from app.db.database import get_db
    from app.main import app

    def old_schema_db():
        raise ProgrammingError("select", {}, Exception("column class_sections.theory_slot_id does not exist"))
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = old_schema_db
    r = client.post("/api/auth/login", json={"email": "a@b.edu", "password": "x"})
    assert r.status_code == 503 and r.json()["code"] == "SCHEMA_OUTDATED" and "DROP SCHEMA" not in r.json()["detail"]
    assert "administrator" in r.json()["detail"]
