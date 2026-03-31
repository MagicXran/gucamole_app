"""
Pydantic 数据模型
"""

from typing import Optional, List, Any

from pydantic import BaseModel, Field, field_validator


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
    # RDP 高级参数
    color_depth: Optional[int] = None
    disable_gfx: bool = True
    resize_method: str = "display-update"
    enable_wallpaper: bool = False
    enable_font_smoothing: bool = True
    disable_copy: bool = False
    disable_paste: bool = False
    enable_audio: bool = True
    enable_audio_input: bool = False
    enable_printing: bool = False
    timezone: Optional[str] = Field(default=None, max_length=50)
    keyboard_layout: Optional[str] = Field(default=None, max_length=50)
    pool_id: Optional[int] = Field(default=None, ge=1)
    member_max_concurrent: int = Field(default=1, ge=1, le=9999)

    @field_validator("color_depth")
    @classmethod
    def check_color_depth(cls, v):
        if v is not None and v not in (8, 16, 24):
            raise ValueError("color_depth 必须是 8, 16, 24 或 null")
        return v

    @field_validator("resize_method")
    @classmethod
    def check_resize_method(cls, v):
        if v not in ("display-update", "reconnect"):
            raise ValueError("resize_method 必须是 display-update 或 reconnect")
        return v


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
    color_depth: Optional[int] = None
    disable_gfx: Optional[bool] = None
    resize_method: Optional[str] = Field(default=None, max_length=20)
    enable_wallpaper: Optional[bool] = None
    enable_font_smoothing: Optional[bool] = None
    disable_copy: Optional[bool] = None
    disable_paste: Optional[bool] = None
    enable_audio: Optional[bool] = None
    enable_audio_input: Optional[bool] = None
    enable_printing: Optional[bool] = None
    timezone: Optional[str] = Field(default=None, max_length=50)
    keyboard_layout: Optional[str] = Field(default=None, max_length=50)
    pool_id: Optional[int] = Field(default=None, ge=1)
    member_max_concurrent: Optional[int] = Field(default=None, ge=1, le=9999)
    is_active: Optional[bool] = None

    @field_validator("color_depth")
    @classmethod
    def check_color_depth(cls, v):
        if v is not None and v not in (8, 16, 24):
            raise ValueError("color_depth 必须是 8, 16, 24 或 null")
        return v

    @field_validator("resize_method")
    @classmethod
    def check_resize_method(cls, v):
        if v is not None and v not in ("display-update", "reconnect"):
            raise ValueError("resize_method 必须是 display-update 或 reconnect")
        return v


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
    color_depth: Optional[int] = None
    disable_gfx: bool = True
    resize_method: str = "display-update"
    enable_wallpaper: bool = False
    enable_font_smoothing: bool = True
    disable_copy: bool = False
    disable_paste: bool = False
    enable_audio: bool = True
    enable_audio_input: bool = False
    enable_printing: bool = False
    timezone: Optional[str] = None
    keyboard_layout: Optional[str] = None
    pool_id: Optional[int] = None
    member_max_concurrent: int = 1
    is_active: bool = True


class UserCreateRequest(BaseModel):
    """创建用户"""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    display_name: str = Field(default="", max_length=100)
    is_admin: bool = False
    quota_gb: Optional[float] = Field(default=None, ge=0, description="个人空间配额(GB), 0=使用默认")


class UserUpdateRequest(BaseModel):
    """修改用户（密码留空=不改）"""
    display_name: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = Field(default=None, min_length=4, max_length=128)
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    quota_gb: Optional[float] = Field(default=None, ge=0, description="个人空间配额(GB), 0=使用默认")


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


class ResourcePoolCardResponse(BaseModel):
    """资源池卡片数据"""
    id: int = Field(..., description="代表性 launch_app_id")
    pool_id: int
    name: str
    icon: str = "desktop"
    protocol: str = "rdp"
    active_count: int = 0
    queued_count: int = 0
    max_concurrent: int = 1
    has_capacity: bool = True


class LaunchQueueConsumeRequest(BaseModel):
    """消费 ready 资格时的请求体"""
    queue_id: Optional[int] = None


class QueueStatusResponse(BaseModel):
    """排队状态响应"""
    queue_id: int
    pool_id: int
    status: str
    position: int = 0
    ready_expires_at: Any = None


class LaunchOrQueueResponse(BaseModel):
    """启动或入队的联合响应"""
    status: str
    redirect_url: str = ""
    connection_name: str = ""
    session_id: str = ""
    queue_id: int = 0
    position: int = 0
    pool_id: int = 0


class ResourcePoolCreateRequest(BaseModel):
    """创建资源池"""
    name: str = Field(..., min_length=1, max_length=200)
    icon: str = Field(default="desktop", max_length=100)
    max_concurrent: int = Field(default=1, ge=1, le=9999)
    auto_dispatch_enabled: bool = True
    dispatch_grace_seconds: int = Field(default=120, ge=10, le=86400)
    stale_timeout_seconds: int = Field(default=120, ge=30, le=86400)
    idle_timeout_seconds: Optional[int] = Field(default=None, ge=60, le=604800)
    is_active: bool = True


class ResourcePoolUpdateRequest(BaseModel):
    """修改资源池"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    icon: Optional[str] = Field(default=None, max_length=100)
    max_concurrent: Optional[int] = Field(default=None, ge=1, le=9999)
    auto_dispatch_enabled: Optional[bool] = None
    dispatch_grace_seconds: Optional[int] = Field(default=None, ge=10, le=86400)
    stale_timeout_seconds: Optional[int] = Field(default=None, ge=30, le=86400)
    idle_timeout_seconds: Optional[int] = Field(default=None, ge=60, le=604800)
    is_active: Optional[bool] = None


class ResourcePoolAdminResponse(BaseModel):
    """资源池管理响应"""
    id: int
    name: str
    icon: str = "desktop"
    max_concurrent: int
    auto_dispatch_enabled: bool = True
    dispatch_grace_seconds: int
    stale_timeout_seconds: int
    idle_timeout_seconds: Optional[int] = None
    is_active: bool = True
    active_count: int = 0
    queued_count: int = 0
