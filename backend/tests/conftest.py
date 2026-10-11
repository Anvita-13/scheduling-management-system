"""Test fixtures.

By default the suite runs on in-memory SQLite so it needs no setup.  To run the identical tests
(including the concurrency tests) against real PostgreSQL set ``TEST_DATABASE_URL``, e.g.
``postgresql+psycopg2://user:pass@localhost:5432/scheduling_test`` - the schema is dropped/recreated.
"""
import os

os.environ.setdefault("BCRYPT_ROUNDS", "4")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-0123456789")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import models as _models  # noqa: F401  (registers all tables on Base.metadata)
from app.db.database import Base, get_db, make_engine
from app.main import app

TEST_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")
IS_POSTGRES = TEST_URL.startswith("postgresql")


@pytest.fixture(scope="session")
def engine():
    eng = make_engine(TEST_URL)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_factory(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db(session_factory):
    s = session_factory()
    yield s
    s.close()


@pytest.fixture()
def client(session_factory):
    def override():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
