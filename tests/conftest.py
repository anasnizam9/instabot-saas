"""
Pytest configuration and fixtures for async tests
"""

import pytest
import pytest_asyncio
from datetime import datetime, UTC
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.db.base import Base
from app.models import User, Organization, OrganizationMember
from app.db.session import get_db
from app.core.security import get_password_hash, create_access_token
from app.core.config import settings


# Create async test database engine
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = None
TestingSessionLocal = None


# Create async test database engine
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = None
TestingSessionLocal = None


async def override_get_db():
    """Override the get_db dependency for testing"""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Setup test database at session start - runs once per test session"""
    global engine, TestingSessionLocal
    
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    
    TestingSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Create all tables once at the beginning of the test session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Drop all tables at the end of the test session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(setup_test_db) -> AsyncSession:
    """Create test database and session"""
    # Just return a new session - tables already created by setup_test_db
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, setup_test_db) -> AsyncClient:
    """Create async test client with database override"""
    app.dependency_overrides[get_db] = override_get_db

    from httpx import ASGITransport
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def user_with_org(db_session: AsyncSession) -> tuple[User, Organization]:
    """Create test user with organization"""
    # Create organization
    org = Organization(
        id=uuid4().hex,
        name="Test Organization",
        created_at=datetime.now(UTC),
    )

    # Create user
    user_id = uuid4().hex
    user = User(
        id=user_id,
        email=f"test-{uuid4().hex[:8]}@example.com",
        full_name="Test User",
        hashed_password=get_password_hash("TestPassword123"),
        created_at=datetime.now(UTC),
    )

    # Create membership (user is owner)
    membership = OrganizationMember(
        id=uuid4().hex,
        user_id=user.id,
        organization_id=org.id,
        role="owner",
        created_at=datetime.now(UTC),
    )

    # Save to database
    db_session.add(org)
    db_session.add(user)
    db_session.add(membership)
    await db_session.commit()

    # Generate a proper JWT token for the user
    access_token = create_access_token(subject=user.id)
    
    # Attach token to user object for test use
    user.access_token = access_token

    yield user, org
