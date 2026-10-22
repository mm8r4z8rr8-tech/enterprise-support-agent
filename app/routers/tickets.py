import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Ticket, User
from app.redis_client import redis_client
from app.schemas import TicketCreate, TicketUpdate, TicketOut
from app.security import get_current_user


router = APIRouter(prefix="/tickets", tags=["工单管理"])

logger = logging.getLogger(__name__)

# 工单列表缓存有效期：60 秒
CACHE_TTL_SECONDS = 60


def _ticket_list_cache_key(
    user_id: int,
    status_filter: str | None,
) -> str:
    """生成当前用户对应的工单列表缓存键。"""
    status_value = status_filter or "all"
    return f"tickets:user:{user_id}:status:{status_value}"


def _invalidate_ticket_list_cache(user_id: int) -> None:
    """清除当前用户的全部工单列表缓存。"""
    cache_keys = [
        _ticket_list_cache_key(user_id, None),
        _ticket_list_cache_key(user_id, "open"),
        _ticket_list_cache_key(user_id, "closed"),
    ]

    try:
        redis_client.delete(*cache_keys)
    except Exception:
        # 缓存清理失败不能影响已经成功提交的数据库操作。
        logger.warning(
            "Failed to invalidate ticket cache for user_id=%s",
            user_id,
            exc_info=True,
        )


@router.post("/", response_model=TicketOut, status_code=201)
def create_ticket(
    ticket_data: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = Ticket(
        title=ticket_data.title,
        description=ticket_data.description,
        priority=ticket_data.priority,
        status="open",
        user_id=current_user.id,
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    _invalidate_ticket_list_cache(current_user.id)

    return ticket


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status: Literal["open", "closed"] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = _ticket_list_cache_key(current_user.id, status)

    # 1. 优先尝试读取 Redis 缓存。
    try:
        cached_data = redis_client.get(cache_key)

        # 注意：空列表 "[]" 也是有效缓存，不能当作缓存未命中。
        if cached_data is not None:
            return json.loads(cached_data)

    except Exception:
        logger.warning(
            "Failed to read ticket cache; falling back to database",
            exc_info=True,
        )

    # 2. 缓存未命中或 Redis 不可用时，查询数据库。
    statement = select(Ticket)

    if status is not None:
        statement = statement.where(Ticket.status == status)

    # 安全关键点：只能查询当前登录用户自己的工单。
    statement = statement.where(Ticket.user_id == current_user.id)

    tickets = db.scalars(statement).all()

    # 3. 将数据库结果转换成可 JSON 序列化的数据，再写入缓存。
    try:
        cache_data = [
            TicketOut.model_validate(ticket).model_dump(mode="json")
            for ticket in tickets
        ]

        redis_client.setex(
            cache_key,
            CACHE_TTL_SECONDS,
            json.dumps(cache_data, ensure_ascii=False),
        )

    except Exception:
        logger.warning(
            "Failed to write ticket cache",
            exc_info=True,
        )

    return tickets


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.scalar(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.user_id == current_user.id,
        )
    )

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int,
    ticket_data: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.scalar(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.user_id == current_user.id,
        )
    )

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    update_data = ticket_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(ticket, field, value)

    db.commit()
    db.refresh(ticket)

    _invalidate_ticket_list_cache(current_user.id)

    return ticket


@router.patch("/{ticket_id}/close", response_model=TicketOut)
def close_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.scalar(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.user_id == current_user.id,
        )
    )

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status == "closed":
        raise HTTPException(status_code=400, detail="Ticket is already closed")

    ticket.status = "closed"

    db.commit()
    db.refresh(ticket)

    _invalidate_ticket_list_cache(current_user.id)

    return ticket


@router.delete("/{ticket_id}")
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.scalar(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.user_id == current_user.id,
        )
    )

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    db.delete(ticket)
    db.commit()

    _invalidate_ticket_list_cache(current_user.id)

    return {
        "message": "Ticket deleted successfully",
        "ticket_id": ticket_id,
    }