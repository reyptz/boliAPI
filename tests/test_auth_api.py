import pytest
import pytest_asyncio
import uuid
from httpx import ASGITransport, AsyncClient
from main import app
from app.presentation.dependencies import get_user_repository
from app.domain.repositories.user_repository import UserRepository
from app.domain.entities.user import UserEntity
from app.domain.enums.user_role import UserRole

# ── Mock InMemoryUserRepository ──────────────────────────────
class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self.users = {}

    async def create(self, user: UserEntity) -> UserEntity:
        if isinstance(user.role, str):
            user.role = UserRole(user.role)
        self.users[user.id] = user
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> UserEntity | None:
        return self.users.get(user_id)

    async def get_by_phone(self, phone: str) -> UserEntity | None:
        for u in self.users.values():
            if u.phone == phone:
                return u
        return None

    async def get_by_email(self, email: str) -> UserEntity | None:
        for u in self.users.values():
            if u.email == email:
                return u
        return None

    async def get_by_username(self, username: str) -> UserEntity | None:
        for u in self.users.values():
            if u.username == username:
                return u
        return None

    async def get_by_reset_token(self, token: str) -> UserEntity | None:
        for u in self.users.values():
            if u.reset_token == token:
                return u
        return None

    async def list_all(self, *, role: str | None = None, offset: int = 0, limit: int = 50):
        items = list(self.users.values())
        if role:
            items = [u for u in items if u.role.value == role]
        return items[offset:offset+limit], len(items)

    async def update(self, user: UserEntity) -> UserEntity:
        if isinstance(user.role, str):
            user.role = UserRole(user.role)
        self.users[user.id] = user
        return user

    async def delete(self, user_id: uuid.UUID) -> bool:
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False

    async def exists_by_phone(self, phone: str) -> bool:
        return any(u.phone == phone for u in self.users.values())

    async def exists_by_email(self, email: str) -> bool:
        return any(u.email == email for u in self.users.values())

    async def exists_by_username(self, username: str) -> bool:
        return any(u.username == username for u in self.users.values())

# Override dependency
mock_repo = InMemoryUserRepository()
app.dependency_overrides[get_user_repository] = lambda: mock_repo

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_signup_and_signin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Signup
        signup_payload = {
            "phone": "+22370000099",
            "password": "TestPassword123",
            "role": "client"
        }
        response = await ac.post("/api/v1/auth/signup", json=signup_payload)
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        
        # Signin
        signin_payload = {
            "identifier": "+22370000099",
            "password": "TestPassword123"
        }
        response = await ac.post("/api/v1/auth/signin", json=signin_payload)
        assert response.status_code == 200
        assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_invalid_signin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        signin_payload = {
            "identifier": "+22370000099",
            "password": "WrongPassword"
        }
        response = await ac.post("/api/v1/auth/signin", json=signin_payload)
        assert response.status_code == 401
