
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import Token, UserLogin, UserOut, UserRegister
from app.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.security import get_current_user

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    # 先检查用户名是否已经存在
    existing_user = db.scalar(
        select(User).where(
            User.username == user_data.username
        )
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # 创建用户对象，只保存密码哈希，不保存原始密码
    user = User(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)

    except IntegrityError:
        # 防止两个并发请求同时注册相同用户名
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    return user

@router.post("/login", response_model=Token)
def login_user(
    user_data: UserLogin,
    db: Session = Depends(get_db),
):
    # 根据用户名查询用户
    user = db.scalar(
        select(User).where(
            User.username == user_data.username
        )
    )

    # 用户不存在或密码错误，都返回相同的错误信息
    # 避免通过错误提示判断某个用户名是否已注册
    if user is None or not verify_password(
        user_data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 登录成功，将用户 ID 写入 JWT 的 sub 字段
    access_token = create_access_token(
        data={"sub": str(user.id)}
    )

    # 返回访问令牌
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.get("/me", response_model=UserOut)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    """返回当前登录用户的信息。"""
    return current_user