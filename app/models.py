
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    # 对应 MySQL 中的 users 表
    __tablename__ = "users"

    # 主键：数据库自动生成用户 ID
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # 用户名：不能为空，且不能重复
    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )

    # 密码哈希：只存哈希结果，不存原始密码
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )


class Ticket(Base):
    # 对应 MySQL 中的 tickets 表
    __tablename__ = "tickets"

    # 主键：数据库自动生成工单 ID
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # 工单标题，最多 100 个字符，不允许为空
    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # 工单详细描述，使用 TEXT 类型存储
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # 工单优先级，默认值为 medium
    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="medium",
    )

    # 工单状态，默认值为 open
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open",
    )
    # 工单所属用户 ID，关联 users 表的主键
    # 暂时允许为空，以兼容数据库中已经存在的旧工单
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )