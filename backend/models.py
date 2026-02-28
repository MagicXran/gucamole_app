"""
Pydantic 数据模型
"""

from datetime import datetime
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
