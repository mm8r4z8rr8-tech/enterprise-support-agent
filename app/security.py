
from pwdlib import PasswordHash

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User



# 创建推荐的密码哈希工具，整个应用复用
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """将原始密码转换为安全的哈希字符串。"""
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """验证用户输入的密码是否与已存储的哈希匹配。"""
    return password_hash.verify(
        plain_password,
        hashed_password,
    )

# 加载项目根目录中的 .env 配置
load_dotenv()

# 读取 JWT 配置
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)

# 没有配置密钥时直接报错，避免使用不安全的默认密钥
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is missing. Please configure it in .env"
    )


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """根据用户数据生成带过期时间的 JWT。"""

    # 复制数据，避免修改调用方传入的字典
    to_encode = data.copy()

    # 计算过期时间，默认有效期为 30 分钟
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # exp 是 JWT 标准的过期时间字段
    to_encode.update({"exp": expire})

    # 使用密钥签名，生成 JWT 字符串
    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """验证 JWT 签名和有效期，并返回令牌中的数据。"""

    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
    )

# 从 Authorization 请求头中提取 Bearer Token
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    """验证 JWT，并获取当前登录用户。"""

    # 没有携带令牌
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(credentials.credentials)

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise credentials_exception

        try:
            user_id = int(subject)
        except ValueError:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # 确认数据库中仍存在这个用户
    user = db.get(User, user_id)

    if user is None:
        raise credentials_exception

    return user