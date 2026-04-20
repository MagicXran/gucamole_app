"""
Pydantic 数据模型
"""

from datetime import datetime
from typing import Optional, List, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


def _normalize_attachment_link_url(value: str) -> str:
    normalized = value.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("link_url 只允许 http/https 绝对链接")
    return normalized


def _normalize_booking_datetime(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("scheduled_for 不能为空")

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("scheduled_for 必须是合法日期时间") from exc

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _normalize_required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} 不能为空")
    return normalized


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
    app_kind: Literal["commercial_software", "simulation_app", "compute_tool"] = "commercial_software"
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
    disable_download: Optional[int] = Field(default=None)
    disable_upload: Optional[int] = Field(default=None)
    timezone: Optional[str] = Field(default=None, max_length=50)
    keyboard_layout: Optional[str] = Field(default=None, max_length=50)
    pool_id: Optional[int] = Field(default=None, ge=1)
    member_max_concurrent: int = Field(default=1, ge=1, le=9999)
    script_enabled: bool = False
    script_profile_key: Optional[str] = Field(default=None, max_length=100)
    script_executor_key: Optional[str] = Field(default=None, max_length=100)
    script_worker_group_id: Optional[int] = Field(default=None, ge=1)
    script_scratch_root: Optional[str] = Field(default=None, max_length=500)
    script_python_executable: Optional[str] = Field(default=None, max_length=500)
    script_python_env: Optional[dict[str, str]] = None

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

    @field_validator("disable_download", "disable_upload")
    @classmethod
    def check_transfer_policy(cls, v):
        if v is not None and v not in (0, 1):
            raise ValueError("传输策略必须是 0, 1 或 null")
        return v

    @field_validator("script_executor_key")
    @classmethod
    def check_script_executor_key(cls, v):
        if v is not None and v not in ("python_api", "command_statusfile"):
            raise ValueError("script_executor_key 必须是 python_api 或 command_statusfile")
        return v


class AppUpdateRequest(BaseModel):
    """修改应用（全部可选）"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    icon: Optional[str] = Field(default=None, max_length=100)
    app_kind: Optional[Literal["commercial_software", "simulation_app", "compute_tool"]] = None
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
    disable_download: Optional[int] = Field(default=None)
    disable_upload: Optional[int] = Field(default=None)
    timezone: Optional[str] = Field(default=None, max_length=50)
    keyboard_layout: Optional[str] = Field(default=None, max_length=50)
    pool_id: Optional[int] = Field(default=None, ge=1)
    member_max_concurrent: Optional[int] = Field(default=None, ge=1, le=9999)
    is_active: Optional[bool] = None
    script_enabled: Optional[bool] = None
    script_profile_key: Optional[str] = Field(default=None, max_length=100)
    script_executor_key: Optional[str] = Field(default=None, max_length=100)
    script_worker_group_id: Optional[int] = Field(default=None, ge=1)
    script_scratch_root: Optional[str] = Field(default=None, max_length=500)
    script_python_executable: Optional[str] = Field(default=None, max_length=500)
    script_python_env: Optional[dict[str, str]] = None

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

    @field_validator("disable_download", "disable_upload")
    @classmethod
    def check_transfer_policy(cls, v):
        if v is not None and v not in (0, 1):
            raise ValueError("传输策略必须是 0, 1 或 null")
        return v

    @field_validator("script_executor_key")
    @classmethod
    def check_script_executor_key(cls, v):
        if v is not None and v not in ("python_api", "command_statusfile"):
            raise ValueError("script_executor_key 必须是 python_api 或 command_statusfile")
        return v


class AppAdminResponse(BaseModel):
    """管理端应用详情"""
    id: int
    name: str
    icon: str
    app_kind: Literal["commercial_software", "simulation_app", "compute_tool"] = "commercial_software"
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
    disable_download: Optional[int] = None
    disable_upload: Optional[int] = None
    timezone: Optional[str] = None
    keyboard_layout: Optional[str] = None
    pool_id: Optional[int] = None
    member_max_concurrent: int = 1
    is_active: bool = True
    script_enabled: bool = False
    script_profile_key: Optional[str] = None
    script_profile_name: Optional[str] = None
    script_executor_key: Optional[str] = None
    script_worker_group_id: Optional[int] = None
    script_scratch_root: Optional[str] = None
    script_python_executable: Optional[str] = None
    script_python_env: Optional[dict[str, str]] = None


class UserCreateRequest(BaseModel):
    """创建用户"""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    display_name: str = Field(default="", max_length=100)
    department: str = Field(default="", max_length=100)
    is_admin: bool = False
    quota_gb: Optional[float] = Field(default=None, ge=0, description="个人空间配额(GB), 0=使用默认")


class UserUpdateRequest(BaseModel):
    """修改用户（密码留空=不改）"""
    display_name: Optional[str] = Field(default=None, max_length=100)
    department: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = Field(default=None, min_length=4, max_length=128)
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    quota_gb: Optional[float] = Field(default=None, ge=0, description="个人空间配额(GB), 0=使用默认")


class UserAdminResponse(BaseModel):
    """管理端用户详情（不含 password_hash）"""
    id: int
    username: str
    display_name: str
    department: str = ""
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


class AnalyticsOverviewCardsResponse(BaseModel):
    software_launches: int = 0
    case_events: int = 0
    active_users: int = 0
    department_count: int = 0


class SoftwareAccessRankingItemResponse(BaseModel):
    app_id: int
    app_name: str
    launch_count: int = 0


class CaseAccessRankingItemResponse(BaseModel):
    case_id: int
    case_uid: str
    case_title: str
    detail_count: int = 0
    download_count: int = 0
    transfer_count: int = 0
    event_count: int = 0


class UserAnalyticsRankingItemResponse(BaseModel):
    user_id: int
    username: str
    display_name: str
    department: str = "未设置"
    software_launch_count: int = 0
    case_event_count: int = 0
    event_count: int = 0


class DepartmentAnalyticsRankingItemResponse(BaseModel):
    department: str
    user_count: int = 0
    event_count: int = 0


class AdminAnalyticsOverviewResponse(BaseModel):
    overview: AnalyticsOverviewCardsResponse
    software_ranking: List[SoftwareAccessRankingItemResponse] = Field(default_factory=list)
    case_ranking: List[CaseAccessRankingItemResponse] = Field(default_factory=list)
    user_ranking: List[UserAnalyticsRankingItemResponse] = Field(default_factory=list)
    department_ranking: List[DepartmentAnalyticsRankingItemResponse] = Field(default_factory=list)


class ResourcePoolCardResponse(BaseModel):
    """资源池卡片数据"""
    id: int = Field(..., description="代表性 launch_app_id")
    pool_id: int
    name: str
    icon: str = "desktop"
    app_kind: Literal["commercial_software", "simulation_app", "compute_tool"] = "commercial_software"
    protocol: str = "rdp"
    supports_gui: bool = True
    supports_script: bool = False
    script_runtime_id: Optional[int] = None
    script_profile_key: Optional[str] = None
    script_profile_name: Optional[str] = None
    script_schedulable: bool = False
    script_status_code: str = ""
    script_status_label: str = ""
    script_status_tone: str = ""
    script_status_summary: str = ""
    script_status_reason: str = ""
    resource_status_code: str = ""
    resource_status_label: str = ""
    resource_status_tone: str = ""
    active_count: int = 0
    queued_count: int = 0
    max_concurrent: int = 1
    has_capacity: bool = True


class AppAttachmentItemResponse(BaseModel):
    id: int
    title: str
    summary: str = ""
    link_url: str
    sort_order: int = 0


class PoolAttachmentResponse(BaseModel):
    pool_id: int
    tutorial_docs: List[AppAttachmentItemResponse] = Field(default_factory=list)
    video_resources: List[AppAttachmentItemResponse] = Field(default_factory=list)
    plugin_downloads: List[AppAttachmentItemResponse] = Field(default_factory=list)


class AppAttachmentUpsertItem(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(default="", max_length=500)
    link_url: str = Field(..., min_length=1, max_length=1000)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("link_url")
    @classmethod
    def check_link_url(cls, value: str) -> str:
        return _normalize_attachment_link_url(value)


class PoolAttachmentUpdateRequest(BaseModel):
    tutorial_docs: List[AppAttachmentUpsertItem] = Field(default_factory=list)
    video_resources: List[AppAttachmentUpsertItem] = Field(default_factory=list)
    plugin_downloads: List[AppAttachmentUpsertItem] = Field(default_factory=list)


class BookingCreateRequest(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=200)
    scheduled_for: str = Field(..., min_length=1, max_length=32)
    purpose: str = Field(..., min_length=1, max_length=255)
    note: str = Field(default="", max_length=1000)

    @field_validator("app_name")
    @classmethod
    def check_app_name(cls, value: str) -> str:
        return _normalize_required_text(value, "app_name")

    @field_validator("scheduled_for")
    @classmethod
    def check_scheduled_for(cls, value: str) -> str:
        return _normalize_booking_datetime(value)

    @field_validator("purpose")
    @classmethod
    def check_purpose(cls, value: str) -> str:
        return _normalize_required_text(value, "purpose")


class BookingRecordResponse(BaseModel):
    id: int
    user_id: int
    app_name: str
    scheduled_for: Any
    purpose: str
    note: str = ""
    status: Literal["active", "cancelled"] | str = "active"
    created_at: Any = None
    cancelled_at: Any = None


class CasePublishRequest(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(default="", max_length=1000)

    @field_validator("task_id", "title")
    @classmethod
    def check_required_case_text(cls, value: str, info) -> str:
        return _normalize_required_text(value, info.field_name)


class CasePublishResponse(BaseModel):
    case_uid: str
    archive_path: str
    asset_count: int


class CaseAssetResponse(BaseModel):
    id: int
    asset_kind: str
    display_name: str
    package_relative_path: str
    size_bytes: Optional[int] = None
    sort_order: int = 0


class CaseListItemResponse(BaseModel):
    id: int
    case_uid: str
    title: str
    summary: str = ""
    app_id: Optional[int] = None
    published_at: Any = None
    asset_count: int = 0


class CaseDetailResponse(CaseListItemResponse):
    assets: List[CaseAssetResponse] = Field(default_factory=list)


class CaseTransferResponse(BaseModel):
    case_id: int
    case_uid: str
    target_path: str
    asset_count: int = 0


class CommentCreateRequest(BaseModel):
    target_type: str = Field(..., min_length=1, max_length=20)
    target_id: int = Field(..., ge=1)
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("target_type")
    @classmethod
    def normalize_target_type(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("content")
    @classmethod
    def normalize_comment_content(cls, value: str) -> str:
        return _normalize_required_text(value, "content")


class CommentItemResponse(BaseModel):
    id: int
    target_type: Literal["app", "case"]
    target_id: int
    user_id: int
    author_name: str
    content: str
    created_at: Any = None


class SdkPackageListItemResponse(BaseModel):
    id: int
    package_kind: Literal["cloud_platform", "simulation_app"]
    name: str
    summary: str = ""
    homepage_url: str = ""


class SdkAssetResponse(BaseModel):
    id: int
    version_id: int
    asset_kind: str
    display_name: str
    download_url: str
    size_bytes: Optional[int] = None
    sort_order: int = 0


class SdkVersionResponse(BaseModel):
    id: int
    package_id: int
    version: str
    release_notes: str = ""
    released_at: Any = None
    assets: List[SdkAssetResponse] = Field(default_factory=list)


class SdkPackageDetailResponse(SdkPackageListItemResponse):
    versions: List[SdkVersionResponse] = Field(default_factory=list)


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
    cancel_reason: Optional[str] = None


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
