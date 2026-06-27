"""
AGRIOS Test Configuration
Provides: async test database session, test client, seeded roles.
"""

import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.auth import Role, User

# ── Test Database ─────────────────────────────────────────────────────────────

TEST_DATABASE_URL = settings.DATABASE_URL.replace("/agrios", "/agrios_test")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Create all tables in the test database before the test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Provides an async test database session, rolled back after each test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provides an async HTTP client wired to the test database."""

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Seeded Data Fixtures ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded_roles(db: AsyncSession) -> dict[str, Role]:
    """Seed all 8 roles into the test database."""
    role_defs = [
        ("super_admin", "Super Admin", True),
        ("platform_admin", "Platform Admin", True),
        ("enterprise_owner", "Enterprise Owner", False),
        ("farm_owner", "Farm Owner", False),
        ("farm_manager", "Farm Manager", False),
        ("vet_consultant", "Vet / Consultant", False),
        ("farm_worker", "Farm Worker", False),
        ("viewer", "Viewer", False),
    ]
    roles = {}
    for name, display_name, is_platform in role_defs:
        role = Role(name=name, display_name=display_name, is_platform_role=is_platform)
        db.add(role)
        roles[name] = role
    await db.flush()
    return roles


@pytest_asyncio.fixture
async def test_user(db: AsyncSession, seeded_roles) -> User:
    """Creates a basic test user with farm_owner role."""
    user = User(
        phone="+254712345678",
        full_name="Test Farmer",
        is_phone_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user
