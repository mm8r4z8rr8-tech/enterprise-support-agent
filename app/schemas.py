from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    """创建工单时接收的请求数据。"""

    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    priority: Literal["low", "medium", "high"] = "medium"


class TicketUpdate(BaseModel):
    """更新工单时接收的请求数据，允许只修改部分字段。"""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )
    priority: Literal["low", "medium", "high"] | None = None


class TicketOut(BaseModel):
    """返回给客户端的工单数据。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    priority: str
    status: str

class UserRegister(BaseModel):
    """用户注册请求体。"""

    username: str = Field(
        min_length=3,
        max_length=50,
    )
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class UserOut(BaseModel):
    """返回给客户端的用户信息，不包含密码或密码哈希。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str

class UserLogin(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"