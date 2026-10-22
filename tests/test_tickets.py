
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app, unhandled_exception_handler
from app.database import Base, get_db
from app import models
from app.redis_client import redis_client
import fnmatch
# ============================================================
# 1. 创建独立的测试数据库
# ============================================================
# 使用内存 SQLite，不操作项目开发环境中的 MySQL。
# StaticPool 确保测试过程复用同一个内存数据库连接。
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)
class FakeRedis:
    """用于测试的内存版 Redis，不需要启动真实 Redis 服务。"""

    def __init__(self):
        self.data = {}
        self.get_calls = 0
        self.setex_calls = 0
        self.raise_on_get = False

    def get(self, key):
        self.get_calls += 1

        if self.raise_on_get:
            raise ConnectionError("Simulated Redis failure")

        return self.data.get(key)

    def setex(self, key, seconds, value):
        self.setex_calls += 1
        self.data[key] = value

    def delete(self, *keys):
        deleted = 0

        for key in keys:
            if key in self.data:
                del self.data[key]
                deleted += 1

        return deleted

    def scan_iter(self, match="*"):
        for key in list(self.data.keys()):
            if fnmatch.fnmatch(key, match):
                yield key

# ============================================================
# 2. 替换 FastAPI 的数据库依赖
# ============================================================
def override_get_db():
    """每次请求使用测试数据库会话。"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# 将项目中的数据库依赖替换为测试数据库。
app.dependency_overrides[get_db] = override_get_db


# ============================================================
# 3. pytest fixture：每个测试使用独立的数据环境
# ============================================================
@pytest.fixture
def client(monkeypatch):
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    fake_redis = FakeRedis()

    # 将工单路由使用的 Redis 客户端替换成模拟对象。
    monkeypatch.setattr(
        "app.routers.tickets.redis_client",
        fake_redis,
    )

    # 保存模拟 Redis，方便测试检查缓存行为。
    app.state.test_redis = fake_redis

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=test_engine)
    app.state.test_redis = None

# ============================================================
# 4. 测试辅助函数：注册用户并登录
# ============================================================
def authenticate_client(client, username="testuser"):
    """
    注册测试用户、登录获取 JWT，并将令牌设置到客户端请求头。

    后续通过这个 client 发出的请求会自动携带 JWT。
    """
    password = "TestPass123!"

    # 第一步：注册用户。
    register_response = client.post(
        "/users/register",
        json={
            "username": username,
            "password": password,
        },
    )

    assert register_response.status_code == 201, (
        f"注册测试用户失败：{register_response.status_code}, "
        f"{register_response.text}"
    )

    # 第二步：登录，获取访问令牌。
    login_response = client.post(
        "/users/login",
        json={
            "username": username,
            "password": password,
        },
    )

    assert login_response.status_code == 200, (
        f"登录测试用户失败：{login_response.status_code}, "
        f"{login_response.text}"
    )

    token = login_response.json()["access_token"]

    # 第三步：设置 Authorization 请求头。
    # 之后 client 发出的请求会自动携带这个 JWT。
    client.headers.update({
        "Authorization": f"Bearer {token}"
    })

    return token


# ============================================================
# 5. 创建工单测试
# ============================================================
def test_create_ticket(client):
    # 先登录，后续工单接口才能通过 JWT 认证。
    authenticate_client(client)

    response = client.post(
        "/tickets/",
        json={
            "title": "登录失败",
            "description": "用户无法登录系统",
            "priority": "high",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["title"] == "登录失败"
    assert data["description"] == "用户无法登录系统"
    assert data["priority"] == "high"
    assert data["status"] == "open"
    assert isinstance(data["id"], int)


def test_create_ticket_missing_title(client):
    """缺少必填标题时，应返回请求校验错误。"""
    authenticate_client(client)

    response = client.post(
        "/tickets/",
        json={
            "description": "用户无法登录系统",
            "priority": "high",
        },
    )

    assert response.status_code == 422


# ============================================================
# 6. 查询工单测试
# ============================================================
def test_list_tickets(client):
    authenticate_client(client)

    # 先创建一条工单。
    create_response = client.post(
        "/tickets/",
        json={
            "title": "登录失败",
            "description": "用户无法登录系统",
            "priority": "high",
        },
    )
    assert create_response.status_code == 201

    # 查询当前登录用户的工单列表。
    response = client.get("/tickets")

    assert response.status_code == 200
    assert "登录失败" in response.text


def test_list_tickets_empty(client):
    """没有工单时，列表接口也应正常返回。"""
    authenticate_client(client)

    response = client.get("/tickets")

    assert response.status_code == 200

    data = response.json()
    assert data == []


def test_list_multiple_tickets(client):
    """验证列表接口可以返回多条工单。"""
    authenticate_client(client)

    titles = ["登录失败", "订单查询失败"]

    for title in titles:
        response = client.post(
            "/tickets/",
            json={
                "title": title,
                "description": "自动化测试工单",
                "priority": "high",
            },
        )
        assert response.status_code == 201

    response = client.get("/tickets")

    assert response.status_code == 200
    for title in titles:
        assert title in response.text


def test_get_ticket_not_found(client):
    """查询不存在的工单，应返回 404。"""
    authenticate_client(client)

    response = client.get("/tickets/99999")

    assert response.status_code == 404


# ============================================================
# 7. 更新工单测试
# ============================================================
def test_update_ticket(client):
    authenticate_client(client)

    # 创建工单。
    create_response = client.post(
        "/tickets/",
        json={
            "title": "登录失败",
            "description": "用户无法登录系统",
            "priority": "low",
        },
    )
    assert create_response.status_code == 201

    ticket_id = create_response.json()["id"]

    # 只更新优先级。
    update_response = client.patch(
        f"/tickets/{ticket_id}",
        json={"priority": "high"},
    )

    assert update_response.status_code == 200

    data = update_response.json()

    # 修改的字段应更新。
    assert data["priority"] == "high"

    # 其他字段应保持原值。
    assert data["title"] == "登录失败"
    assert data["description"] == "用户无法登录系统"
    assert data["status"] == "open"


def test_update_ticket_not_found(client):
    """更新不存在的工单，应返回 404。"""
    authenticate_client(client)

    response = client.patch(
        "/tickets/99999",
        json={"priority": "high"},
    )

    assert response.status_code == 404


# ============================================================
# 8. 关闭工单测试
# ============================================================
def test_close_ticket(client):
    authenticate_client(client)

    # 创建工单。
    create_response = client.post(
        "/tickets/",
        json={
            "title": "登录失败",
            "description": "用户无法登录系统",
            "priority": "high",
        },
    )
    assert create_response.status_code == 201

    ticket_id = create_response.json()["id"]

    # 关闭工单。
    close_response = client.patch(
        f"/tickets/{ticket_id}/close"
    )

    assert close_response.status_code == 200
    assert close_response.json()["status"] == "closed"


def test_close_ticket_not_found(client):
    """关闭不存在的工单，应返回 404。"""
    authenticate_client(client)

    response = client.patch("/tickets/99999/close")

    assert response.status_code == 404


def test_close_ticket_twice(client):
    """本项目约定：重复关闭返回 400。"""
    authenticate_client(client)

    create_response = client.post(
        "/tickets/",
        json={
            "title": "重复关闭测试",
            "description": "测试工单状态流转",
            "priority": "high",
        },
    )
    assert create_response.status_code == 201

    ticket_id = create_response.json()["id"]

    # 第一次关闭，应成功。
    first_response = client.patch(
        f"/tickets/{ticket_id}/close"
    )
    assert first_response.status_code == 200
    assert first_response.json()["status"] == "closed"

    # 第二次关闭，应返回 400。
    second_response = client.patch(
        f"/tickets/{ticket_id}/close"
    )
    assert second_response.status_code == 400


# ============================================================
# 9. 删除工单测试
# ============================================================
def test_delete_ticket(client):
    authenticate_client(client)

    # 创建工单。
    create_response = client.post(
        "/tickets/",
        json={
            "title": "待删除工单",
            "description": "用于测试删除",
            "priority": "high",
        },
    )
    assert create_response.status_code == 201

    ticket_id = create_response.json()["id"]

    # 删除工单。
    delete_response = client.delete(
        f"/tickets/{ticket_id}"
    )
    assert delete_response.status_code == 200

    # 删除后再次查询，应返回 404。
    get_response = client.get(
        f"/tickets/{ticket_id}"
    )
    assert get_response.status_code == 404


def test_delete_ticket_not_found(client):
    """删除不存在的工单，应返回 404。"""
    authenticate_client(client)

    response = client.delete("/tickets/99999")

    assert response.status_code == 404


# ============================================================
# 10. 未登录访问测试
# ============================================================
def test_list_tickets_without_token(client):
    """未携带 JWT 时，访问工单列表应返回 401。"""
    response = client.get("/tickets")

    assert response.status_code == 401


# ============================================================
# 11. 统一异常处理测试
# ============================================================
def test_unhandled_exception_returns_500():
    # 创建一个独立的测试应用，避免影响正式应用路由。
    test_app = FastAPI()

    # 注册项目中的统一异常处理器。
    test_app.add_exception_handler(
        Exception,
        unhandled_exception_handler,
    )

    # 创建一个故意抛出异常的测试接口。
    @test_app.get("/test-error")
    def trigger_error():
        raise RuntimeError("This is a test exception")

    # 禁止测试客户端重新抛出服务端异常，
    # 以便检查实际返回的 HTTP 500 响应。
    with TestClient(
        test_app,
        raise_server_exceptions=False,
    ) as test_client:
        response = test_client.get("/test-error")

    # 验证统一异常处理是否生效。
    assert response.status_code == 500
    assert response.json() == {
        "detail": "Internal server error"
    }

def test_ticket_list_cache_hit(client):
    """第一次查询写入缓存，第二次查询命中缓存。"""
    authenticate_client(client)

    create_response = client.post(
        "/tickets/",
        json={
            "title": "缓存测试",
            "description": "验证 Redis 缓存命中",
            "priority": "high",
        },
    )
    assert create_response.status_code == 201

    cache = client.app.state.test_redis

    first_response = client.get("/tickets")
    assert first_response.status_code == 200
    assert len(first_response.json()) == 1

    writes_after_first_request = cache.setex_calls
    assert writes_after_first_request == 1

    second_response = client.get("/tickets")
    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()

    # 第二次查询直接使用缓存，不应再次写入缓存。
    assert cache.setex_calls == writes_after_first_request


def test_ticket_list_cache_invalidated_after_create(client):
    """创建工单后，之前缓存的空列表应失效。"""
    authenticate_client(client)

    cache = client.app.state.test_redis

    # 第一次查询缓存空列表。
    first_response = client.get("/tickets")
    assert first_response.status_code == 200
    assert first_response.json() == []

    # 创建工单会清除当前用户的列表缓存。
    create_response = client.post(
        "/tickets/",
        json={
            "title": "新工单",
            "description": "验证缓存失效",
            "priority": "medium",
        },
    )
    assert create_response.status_code == 201

    # 再次查询应从数据库获取新工单。
    second_response = client.get("/tickets")
    assert second_response.status_code == 200
    assert len(second_response.json()) == 1
    assert second_response.json()[0]["title"] == "新工单"


def test_ticket_list_falls_back_when_redis_read_fails(client):
    """Redis 读取失败时，仍然可以从数据库获取工单。"""
    authenticate_client(client)

    cache = client.app.state.test_redis
    cache.raise_on_get = True

    response = client.get("/tickets")

    assert response.status_code == 200
    assert response.json() == []