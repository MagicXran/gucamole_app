"""
Portal 用户认证模块 - JWT 登录与验证
"""

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.database import db, CONFIG
from backend.models import LoginRequest, LoginResponse, UserInfo

logger = logging.getLogger(__name__)

_auth_cfg = CONFIG.get("auth", {})
JWT_SECRET = _auth_cfg.get("jwt_secret", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = _auth_cfg.get("token_expire_minutes", 480)

_bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与 bcrypt 哈希"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _create_token(user_id: int, username: str, display_name: str) -> str:
    """生成 JWT"""
    payload = {
        "user_id": user_id,
        "username": username,
        "display_name": display_name,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> UserInfo:
    """FastAPI 依赖: 从 JWT 提取当前用户信息"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
        )
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        return UserInfo(
            user_id=payload["user_id"],
            username=payload["username"],
            display_name=payload.get("display_name", ""),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期，请重新登录",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
        )


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """用户登录，返回 JWT"""
    query = """
        SELECT id, username, password_hash, display_name
        FROM portal_user
        WHERE username = %(username)s AND is_active = 1
    """
    user = db.execute_query(query, {"username": req.username}, fetch_one=True)
    if not user or not _verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = _create_token(user["id"], user["username"], user["display_name"])
    return LoginResponse(
        token=token,
        user_id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
    )
