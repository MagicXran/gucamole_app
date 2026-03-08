"""
Pydantic 数据模型
"""

from typing import Optional, List, Any

from pydantic import BaseModel, Field


class RemoteAppResponse(BaseModel):
    """RemoteApp 卡片数据"""
    id: int
    name: str
    icon: str = "desktop"
    protocol: str = "rdp"
    hostname: str
    port: int = 3389
    remote_app: Optional[str] = None
    is_active: bool = True


class LaunchResponse(BaseModel):
    """启动连接响应"""
    redirect_url: str = Field(..., description="Guacamole 客户端重定向 URL")
    connection_name: str = Field(..., description="连接名称")
    session_id: str = Field("", description="实时监控会话 ID")


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    """登录响应"""
    token: str
    user_id: int
    username: str
    display_name: str
    is_admin: bool = False


class UserInfo(BaseModel):
    """JWT 中的用户信息"""
    user_id: int
    username: str
    display_name: str = ""
    is_admin: bool = False


# ---- 管理后台模型 ----

class AppCreateRequest(BaseModel):
    """创建应用"""
    name: str = Field(..., min_length=1, max_length=200)
    icon: str = Field(default="desktop", max_length=100)
    protocol: str = Field(default="rdp", max_length=20)
    hostname: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=3389, ge=1, le=65535)
    rdp_username: str = Field(default="", max_length=100)
    rdp_password: str = Field(default="", max_length=200)
    domain: str = Field(default="", max_length=100)
    security: str = Field(default="nla", max_length=20)
    ignore_cert: bool = True
    remote_app: str = Field(default="", max_length=200)
    remote_app_dir: str = Field(default="", max_length=500)
    remote_app_args: str = Field(default="", max_length=500)


class AppUpdateRequest(BaseModel):
    """修改应用（全部可选）"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    icon: Optional[str] = Field(default=None, max_length=100)
    hostname: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    rdp_username: Optional[str] = Field(default=None, max_length=100)
    rdp_password: Optional[str] = Field(default=None, max_length=200)
    domain: Optional[str] = Field(default=None, max_length=100)
    security: Optional[str] = Field(default=None, max_length=20)
    ignore_cert: Optional[bool] = None
    remote_app: Optional[str] = Field(default=None, max_length=200)
    remote_app_dir: Optional[str] = Field(default=None, max_length=500)
    remote_app_args: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None


class AppAdminResponse(BaseModel):
    """管理端应用详情"""
    id: int
    name: str
    icon: str
    protocol: str
    hostname: str
    port: int
    rdp_username: Optional[str] = None
    rdp_password: Optional[str] = None
    domain: Optional[str] = None
    security: Optional[str] = None
    ignore_cert: bool = True
    remote_app: Optional[str] = None
    remote_app_dir: Optional[str] = None
    remote_app_args: Optional[str] = None
    is_active: bool = True


class UserCreateRequest(BaseModel):
    """创建用户"""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    display_name: str = Field(default="", max_length=100)
    is_admin: bool = False


class UserUpdateRequest(BaseModel):
    """修改用户（密码留空=不改）"""
    display_name: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = Field(default=None, min_length=4, max_length=128)
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


class UserAdminResponse(BaseModel):
    """管理端用户详情（不含 password_hash）"""
    id: int
    username: str
    display_name: str
    is_admin: bool
    is_active: bool


class AclUpdateRequest(BaseModel):
    """权限覆盖更新"""
    app_ids: List[int]


class AuditLogResponse(BaseModel):
    """审计日志条目"""
    id: int
    user_id: int
    username: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    detail: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Any = None


class PaginatedResponse(BaseModel):
    """分页响应"""
    items: List[Any]
    total: int
    page: int
    page_size: int
