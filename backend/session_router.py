from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.identity_access import resolve_session_context

router = APIRouter(prefix="/api/session", tags=["session"])


class SessionUserPayload(BaseModel):
    user_id: int
    username: str
    display_name: str = ""
    is_admin: bool = False


class SessionMenuNode(BaseModel):
    key: str
    title: str
    path: str | None = None
    children: list["SessionMenuNode"] = Field(default_factory=list)


class SessionBootstrapResponse(BaseModel):
    authenticated: bool = False
    user: SessionUserPayload | None = None
    auth_source: str
    capabilities: list[str] = Field(default_factory=list)
    menu_tree: list[SessionMenuNode] = Field(default_factory=list)
    org_context: dict[str, Any] = Field(default_factory=dict)


@router.get("/bootstrap", response_model=SessionBootstrapResponse)
def session_bootstrap(request: Request):
    return resolve_session_context(request)
