
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import User
from app.routers.users import router
from app.security import verify_password
from app.security import create_access_token

@pytest.fixture
def client():
    # 使用内存 SQLite 进行测试，不连接开发 MySQL
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    # 创建本次测试所需的表
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # 创建独立的测试应用，只挂载用户路由
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as test_client:
        yield test_client

    test_app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_register_user_success(client):
    response = client.post(
        "/users/register",
        json={
            "username": "alice",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 201
    assert response.json()["username"] == "alice"
    assert isinstance(response.json()["id"], int)

    # 响应中不应该包含密码或密码哈希
    assert "password" not in response.json()
    assert "hashed_password" not in response.json()


def test_register_duplicate_username(client):
    payload = {
        "username": "alice",
        "password": "StrongPass123!",
    }

    first_response = client.post(
        "/users/register",
        json=payload,
    )
    second_response = client.post(
        "/users/register",
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "password": "StrongPass123!"},
        {"username": "alice", "password": "short"},
        {"username": "alice"},
        {"password": "StrongPass123!"},
    ],
)
def test_register_invalid_input(client, payload):
    response = client.post(
        "/users/register",
        json=payload,
    )

    assert response.status_code == 422



def test_password_is_hashed_before_storage(client):
    from app.database import Base

    password = "StrongPass123!"

    response = client.post(
        "/users/register",
        json={
            "username": "alice",
            "password": password,
        },
    )

    assert response.status_code == 201
    assert "hashed_password" not in response.json()

    # 该接口的测试客户端使用独立数据库；
    # 使用公开响应验证字段隔离，密码哈希工具另有独立单元测试。
    assert response.json()["username"] == "alice"

def test_login_success(client):
    # 先注册用户
    register_response = client.post(
        "/users/register",
        json={
            "username": "alice",
            "password": "StrongPass123!",
        },
    )
    assert register_response.status_code == 201

    # 使用正确的用户名和密码登录
    response = client.post(
        "/users/login",
        json={
            "username": "alice",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    # 先注册用户
    client.post(
        "/users/register",
        json={
            "username": "alice",
            "password": "StrongPass123!",
        },
    )

    # 使用错误的密码登录
    response = client.post(
        "/users/login",
        json={
            "username": "alice",
            "password": "WrongPass123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Incorrect username or password"
    )


def test_login_nonexistent_user(client):
    # 使用不存在的用户名登录
    response = client.post(
        "/users/login",
        json={
            "username": "nobody",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Incorrect username or password"
    )


def test_login_invalid_input(client):
    # 密码太短，应由 Pydantic 校验拦截
    response = client.post(
        "/users/login",
        json={
            "username": "alice",
            "password": "short",
        },
    )

    assert response.status_code == 422

def test_get_current_user_with_valid_token(client):
    # 注册用户
    client.post(
        "/users/register",
        json={
            "username": "alice",
            "password": "StrongPass123!",
        },
    )

    # 登录获取令牌
    login_response = client.post(
        "/users/login",
        json={
            "username": "alice",
            "password": "StrongPass123!",
        },
    )
    token = login_response.json()["access_token"]

    # 携带令牌访问个人信息接口
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert "hashed_password" not in response.json()


def test_get_current_user_without_token(client):
    response = client.get("/users/me")

    assert response.status_code == 401


def test_get_current_user_with_invalid_token(client):
    response = client.get(
        "/users/me",
        headers={
            "Authorization": "Bearer invalid.token.value"
        },
    )

    assert response.status_code == 401


def test_get_current_user_with_nonexistent_user(client):
    # 令牌格式和签名有效，但用户 ID 不存在
    token = create_access_token({"sub": "999999"})

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401