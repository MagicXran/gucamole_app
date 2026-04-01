"""
Portal 用户认证模块 - JWT 登录与验证
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.database import db, CONFIG
from backend.models import LoginRequest, LoginResponse, UserInfo
from backend.audit import log_action
from backend.structured_logging import log_event

logger = logging.getLogger(__name__)

_auth_cfg = CONFIG.get("auth", {})
JWT_SECRET = _auth_cfg.get("jwt_secret", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = _auth_cfg.get("token_expire_minutes", 480)

_bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---- 速率限制 (滑动窗口, 内存实现) ----

class _RateLimiter:
    """IP 级滑动窗口速率限制器"""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self._max = max_attempts
        self._window = window_seconds
        self._lock = threading.Lock()
        self._attempts: dict[str, list[float]] = {}

    def check(self, key: str) -> bool:
        """检查是否允许请求。返回 True 表示放行，False 表示限流。"""
        now = time.time()
        cutoff = now - self._window
        with self._lock:
            timestamps = self._attempts.get(key, [])
            # 清理过期记录
            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self._max:
                self._attempts[key] = timestamps
                return False
            timestamps.append(now)
            self._attempts[key] = timestamps
            return True


_login_limiter = _RateLimiter(max_attempts=5, window_seconds=60)


def _verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与 bcrypt 哈希"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _create_token(user_id: int, username: str, display_name: str, is_admin: bool) -> str:
    """生成 JWT"""
    payload = {
        "user_id": user_id,
        "username": username,
        "display_name": display_name,
        "is_admin": is_admin,
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
            is_admin=payload.get("is_admin", False),
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


def require_admin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """FastAPI 依赖: 要求管理员权限"""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request):
    """用户登录，返回 JWT"""
    # 速率限制: 每个 IP 每分钟最多 5 次登录尝试
    client_ip = request.client.host if request.client else "unknown"
    if not _login_limiter.check(client_ip):
        log_event(
            logger,
            logging.WARNING,
            "login_rate_limited",
            username=req.username,
            client_ip=client_ip,
            request_id=getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请 1 分钟后再试",
        )

    query = """
        SELECT id, username, password_hash, display_name, is_admin
        FROM portal_user
        WHERE username = %(username)s AND is_active = 1
    """
    user = db.execute_query(query, {"username": req.username}, fetch_one=True)
    if not user or not _verify_password(req.password, user["password_hash"]):
        log_event(
            logger,
            logging.WARNING,
            "login_failed",
            username=req.username,
            client_ip=client_ip,
            request_id=getattr(request.state, "request_id", None),
        )
        # 审计: 登录失败
        log_action(
            user_id=0, username=req.username, action="login_failed",
            ip_address=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    is_admin = bool(user.get("is_admin", 0))
    token = _create_token(user["id"], user["username"], user["display_name"], is_admin)

    # 审计: 登录成功
    log_action(
        user_id=user["id"], username=user["username"], action="login",
        ip_address=client_ip,
    )
    log_event(
        logger,
        logging.INFO,
        "login_succeeded",
        user_id=int(user["id"]),
        username=user["username"],
        client_ip=client_ip,
        is_admin=is_admin,
        request_id=getattr(request.state, "request_id", None),
    )

    return LoginResponse(
        token=token,
        user_id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
        is_admin=is_admin,
    )
