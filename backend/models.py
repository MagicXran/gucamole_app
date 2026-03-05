"""
Pydantic 数据模型
"""

from typing import Optional

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


class UserInfo(BaseModel):
    """JWT 中的用户信息"""
    user_id: int
    username: str
    display_name: str = ""
