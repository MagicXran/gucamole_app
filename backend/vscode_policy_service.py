"""受限 VSCode 控制策略的目录、校验和数据库服务。"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Any
from urllib.parse import urlsplit


POLICY_VERSION = 1
SECURITY_MODES = ("restricted_remoteapp", "restricted_vscode", "admin_desktop")
FIXED_USER_DATA_ROOT = r"C:\PortalProfiles"
FIXED_EXTENSIONS_ROOT = r"C:\PortalExtensions"
FIXED_WORKSPACE = r"\\tsclient\用户数据目录"


CONTROL_CATALOG: tuple[dict[str, Any], ...] = (
    {"code": "workspace_file_ops", "category": "workspace", "label": "用户数据目录文件操作", "enforcement": "Portal + NTFS", "risk": "允许在个人用户数据目录中新建、读写、删除和重命名文件。"},
    {"code": "multi_root_workspace", "category": "workspace", "label": "多根工作区", "enforcement": "VSCode policy", "risk": "工作区仍必须位于允许的用户数据目录路径。"},
    {"code": "user_settings", "category": "personalization", "label": "用户设置", "enforcement": "VSCode profile", "risk": "设置写入当前门户用户的独立 user-data 目录。"},
    {"code": "workspace_settings", "category": "personalization", "label": "工作区设置", "enforcement": "VSCode policy", "risk": "工作区设置可能改变任务和扩展行为。"},
    {"code": "keybindings", "category": "personalization", "label": "快捷键", "enforcement": "VSCode profile", "risk": "允许用户保存自定义快捷键。"},
    {"code": "snippets", "category": "personalization", "label": "代码片段", "enforcement": "VSCode profile", "risk": "代码片段只作为文本配置保存。"},
    {"code": "terminal", "category": "execution", "label": "集成终端", "enforcement": "AppLocker", "risk": "只能启动允许的 shell。"},
    {"code": "tasks", "category": "execution", "label": "Tasks", "enforcement": "VSCode + AppLocker", "risk": "任务只能调用允许的工具链。"},
    {"code": "run", "category": "execution", "label": "运行程序", "enforcement": "AppLocker", "risk": "只能运行登记的可执行文件。"},
    {"code": "build", "category": "execution", "label": "构建/编译", "enforcement": "AppLocker", "risk": "只能运行登记的编译器和构建工具。"},
    {"code": "debug", "category": "execution", "label": "调试", "enforcement": "AppLocker", "risk": "只能运行登记的调试器。"},
    {"code": "git_local", "category": "source_control", "label": "Git 本地操作", "enforcement": "AppLocker", "risk": "只允许登记的 Git 客户端。"},
    {"code": "git_remote", "category": "source_control", "label": "Git 远程操作", "enforcement": "AppLocker + Firewall", "risk": "还需要允许的 Git 网络目标。"},
    {"code": "package_install", "category": "packages", "label": "包安装", "enforcement": "AppLocker + Firewall", "risk": "只允许登记的包管理器和仓库。"},
    {"code": "extension_use", "category": "extensions", "label": "运行批准扩展", "enforcement": "VSCode enterprise policy", "risk": "只运行管理员审核的扩展。"},
    {"code": "extension_install_update", "category": "extensions", "label": "安装/更新批准扩展", "enforcement": "VSCode enterprise policy + Firewall", "risk": "只能安装或更新 allowlist 中的扩展。"},
    {"code": "ai_chat", "category": "ai", "label": "AI Chat", "enforcement": "VSCode enterprise policy + Firewall", "risk": "只允许已审核扩展和网络目标。"},
    {"code": "agent_mode", "category": "ai", "label": "Agent Mode", "enforcement": "VSCode enterprise policy + AppLocker", "risk": "工具调用仍受程序白名单约束。"},
    {"code": "mcp_tools", "category": "ai", "label": "MCP 工具", "enforcement": "VSCode enterprise policy + AppLocker + Firewall", "risk": "MCP 服务和子进程必须登记。"},
    {"code": "integrated_browser", "category": "browser", "label": "集成浏览器", "enforcement": "VSCode policy + Firewall", "risk": "访问范围受网络目标白名单约束。"},
    {"code": "port_forwarding", "category": "network", "label": "端口转发", "enforcement": "VSCode policy + Firewall", "risk": "只允许登记的目标和端口。"},
    {"code": "remote_development", "category": "remote", "label": "远程开发", "enforcement": "AppLocker + Firewall", "risk": "SSH、WSL 或容器工具必须登记。"},
    {"code": "copy_remote_to_local", "category": "data_channel", "label": "远程复制到本地", "enforcement": "Guacamole", "risk": "允许远程剪贴板内容复制到浏览器本地。"},
    {"code": "paste_local_to_remote", "category": "data_channel", "label": "本地粘贴到远程", "enforcement": "Guacamole", "risk": "允许浏览器本地剪贴板写入远程会话。"},
    {"code": "browser_upload", "category": "data_channel", "label": "浏览器上传", "enforcement": "Guacamole", "risk": "允许浏览器向用户数据目录上传文件。"},
    {"code": "browser_download", "category": "data_channel", "label": "浏览器下载", "enforcement": "Guacamole", "risk": "允许从用户数据目录下载到浏览器。"},
    {"code": "printing", "category": "device", "label": "虚拟打印", "enforcement": "Guacamole", "risk": "允许生成可下载的打印文件。"},
    {"code": "audio_output", "category": "device", "label": "音频输出", "enforcement": "Guacamole", "risk": "允许远程音频输出到浏览器。"},
    {"code": "audio_input", "category": "device", "label": "麦克风输入", "enforcement": "Guacamole", "risk": "允许浏览器麦克风输入远程会话。"},
    {"code": "network_git", "category": "network", "label": "Git 服务网络", "enforcement": "Firewall", "risk": "只允许登记的 Git 服务目标。"},
    {"code": "network_packages", "category": "network", "label": "包仓库网络", "enforcement": "Firewall", "risk": "只允许登记的包仓库目标。"},
    {"code": "network_business", "category": "network", "label": "许可证/业务网络", "enforcement": "Firewall", "risk": "只允许登记的许可证和业务服务。"},
    {"code": "network_https", "category": "network", "label": "已登记 HTTPS 目标", "enforcement": "Firewall", "risk": "不代表任意互联网访问。"},
)

CONTROL_CODES = tuple(item["code"] for item in CONTROL_CATALOG)
DEFAULT_PERMISSIONS = {code: True for code in CONTROL_CODES}

LOCKED_BASELINE = (
    {"code": "remoteapp_only", "label": "RemoteApp-only，禁止回退完整桌面"},
    {"code": "personal_guacdrive", "label": "驱动器固定为 /drive/portal_u{user_id}"},
    {"code": "safe_user_id_expansion", "label": "只展开固定 {user_id} 占位符"},
    {"code": "fixed_profile_roots", "label": "user-data/extensions 根目录固定并校验"},
    {"code": "guacdrive_workspace", "label": "默认业务工作区为 \\\\tsclient\\用户数据目录"},
    {"code": "program_allowlist", "label": "shell、工具链和调试器必须显式白名单"},
    {"code": "extension_allowlist", "label": "扩展必须显式白名单"},
    {"code": "network_allowlist", "label": "网络目标必须显式白名单"},
    {"code": "connection_domain_separation", "label": "普通用户和管理员连接域分离"},
    {"code": "audit_and_cache_invalidation", "label": "策略变化写审计并失效 Guacamole session cache"},
)

ALLOWLIST_DEPENDENCIES = {
    "allowed_shells": {"terminal"},
    "allowed_tools": {"tasks", "run", "build", "git_local", "git_remote", "package_install", "agent_mode", "mcp_tools", "remote_development"},
    "allowed_debuggers": {"debug"},
    "allowed_extensions": {"extension_use", "extension_install_update", "ai_chat", "agent_mode", "mcp_tools", "integrated_browser", "port_forwarding", "remote_development"},
    "allowed_network_targets": {"git_remote", "package_install", "extension_install_update", "ai_chat", "mcp_tools", "integrated_browser", "port_forwarding", "remote_development", "network_git", "network_packages", "network_business", "network_https"},
}

_UNKNOWN_PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")
_DANGEROUS_ARGUMENT_CHARS = frozenset("\r\n&|<>^%")


class VscodePolicyError(ValueError):
    """策略无效或无法绑定。"""


def catalog_payload() -> dict[str, Any]:
    controls = []
    for item in CONTROL_CATALOG:
        controls.append(
            {
                **item,
                "requires_allowlists": [
                    field_name
                    for field_name, control_codes in ALLOWLIST_DEPENDENCIES.items()
                    if item["code"] in control_codes
                ],
            }
        )
    return {
        "policy_version": POLICY_VERSION,
        "controls": controls,
        "default_permissions": dict(DEFAULT_PERMISSIONS),
        "locked_baseline": [dict(item) for item in LOCKED_BASELINE],
    }


def _parse_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise VscodePolicyError("策略 JSON 格式无效") from exc
    raise VscodePolicyError("策略 JSON 类型无效")


def normalize_permissions(value: Any, *, default_if_missing: bool = False) -> dict[str, bool]:
    if value is None and default_if_missing:
        return dict(DEFAULT_PERMISSIONS)
    raw = _parse_json(value, {})
    if not isinstance(raw, dict):
        raise VscodePolicyError("permissions 必须是对象")
    unknown = sorted(set(raw) - set(CONTROL_CODES))
    missing = sorted(set(CONTROL_CODES) - set(raw))
    if unknown:
        raise VscodePolicyError(f"存在未知控制项: {', '.join(unknown)}")
    if missing:
        raise VscodePolicyError(f"缺少控制项: {', '.join(missing)}")
    return {code: bool(raw[code]) for code in CONTROL_CODES}


def normalize_allowlist(value: Any, field_name: str) -> list[str]:
    raw = _parse_json(value, [])
    if not isinstance(raw, list):
        raise VscodePolicyError(f"{field_name} 必须是数组")
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        normalized = str(item).strip()
        if not normalized:
            continue
        if "*" in normalized:
            raise VscodePolicyError(f"{field_name} 不允许使用 * 通配")
        if any(char in normalized for char in "\r\n\0"):
            raise VscodePolicyError(f"{field_name} 包含控制字符")
        if field_name in {"allowed_shells", "allowed_tools", "allowed_debuggers"}:
            normalized = _normalize_executable_path(normalized, field_name)
        elif field_name == "allowed_extensions":
            normalized = _normalize_extension_id(normalized)
        elif field_name == "allowed_network_targets":
            normalized = _normalize_network_target(normalized)
        key = normalized.casefold()
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _normalize_executable_path(value: str, field_name: str) -> str:
    if any(char in value for char in _DANGEROUS_ARGUMENT_CHARS) or '"' in value or "{" in value or "}" in value:
        raise VscodePolicyError(f"{field_name} 包含危险字符")
    path = PureWindowsPath(value)
    if not path.is_absolute() or value.startswith("\\\\") or ".." in path.parts:
        raise VscodePolicyError(f"{field_name} 必须使用 Windows 本地绝对路径")
    if path.suffix.casefold() not in {".exe", ".com", ".cmd", ".bat", ".ps1"}:
        raise VscodePolicyError(f"{field_name} 必须指向可执行文件或脚本")
    return str(path)


def _normalize_extension_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*\.[A-Za-z0-9][A-Za-z0-9.-]*", value):
        raise VscodePolicyError("allowed_extensions 必须使用 publisher.extension 标识")
    return value.lower()


def _normalize_network_target(value: str) -> str:
    if "://" in value:
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise VscodePolicyError("allowed_network_targets 只允许 http/https URL")
        try:
            parsed.port
        except ValueError as exc:
            raise VscodePolicyError("allowed_network_targets 端口无效") from exc
        return value

    if "/" in value:
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise VscodePolicyError("allowed_network_targets CIDR 无效") from exc
        return value

    parsed = urlsplit(f"//{value}")
    if not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise VscodePolicyError("allowed_network_targets 必须是 HOST、HOST:PORT、CIDR 或 http/https URL")
    try:
        parsed.port
    except ValueError as exc:
        raise VscodePolicyError("allowed_network_targets 端口无效") from exc
    return value.lower()


def _normalize_fixed_windows_root(value: Any, field_name: str, expected_root: str) -> str:
    normalized = str(value or "").strip().rstrip("\\/")
    if not normalized:
        raise VscodePolicyError(f"{field_name} 不能为空")
    if any(char in normalized for char in _DANGEROUS_ARGUMENT_CHARS) or '"' in normalized or "{" in normalized or "}" in normalized:
        raise VscodePolicyError(f"{field_name} 包含危险字符")
    path = PureWindowsPath(normalized)
    if not path.is_absolute() or normalized.startswith("\\\\") or ".." in path.parts:
        raise VscodePolicyError(f"{field_name} 必须是 Windows 本地绝对路径")
    expected = PureWindowsPath(expected_root)
    if str(path).casefold() != str(expected).casefold():
        raise VscodePolicyError(f"{field_name} 必须固定为 {expected_root}")
    return str(expected)


def _normalize_workspace(value: Any) -> str:
    normalized = str(value or "").strip()
    if normalized != FIXED_WORKSPACE:
        raise VscodePolicyError("default_workspace_template 必须固定为 \\\\tsclient\\用户数据目录")
    return normalized


def normalize_profile_document(payload: dict[str, Any], *, default_permissions: bool = False) -> dict[str, Any]:
    permissions = normalize_permissions(payload.get("permissions"), default_if_missing=default_permissions)
    normalized = {
        "profile_key": str(payload.get("profile_key") or "").strip(),
        "display_name": str(payload.get("display_name") or "").strip(),
        "description": str(payload.get("description") or "").strip(),
        "policy_version": int(payload.get("policy_version") or POLICY_VERSION),
        "is_active": bool(payload.get("is_active", False)),
        "permissions": permissions,
        "allowed_shells": normalize_allowlist(payload.get("allowed_shells"), "allowed_shells"),
        "allowed_tools": normalize_allowlist(payload.get("allowed_tools"), "allowed_tools"),
        "allowed_debuggers": normalize_allowlist(payload.get("allowed_debuggers"), "allowed_debuggers"),
        "allowed_extensions": normalize_allowlist(payload.get("allowed_extensions"), "allowed_extensions"),
        "allowed_network_targets": normalize_allowlist(payload.get("allowed_network_targets"), "allowed_network_targets"),
        "user_data_root": _normalize_fixed_windows_root(payload.get("user_data_root"), "user_data_root", FIXED_USER_DATA_ROOT),
        "extensions_root": _normalize_fixed_windows_root(payload.get("extensions_root"), "extensions_root", FIXED_EXTENSIONS_ROOT),
        "default_workspace_template": _normalize_workspace(payload.get("default_workspace_template")),
    }
    if not normalized["profile_key"]:
        raise VscodePolicyError("profile_key 不能为空")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,99}", normalized["profile_key"]):
        raise VscodePolicyError("profile_key 只允许小写字母、数字、下划线和短横线")
    if not normalized["display_name"]:
        raise VscodePolicyError("display_name 不能为空")
    if normalized["policy_version"] != POLICY_VERSION:
        raise VscodePolicyError(f"policy_version 必须为 {POLICY_VERSION}")
    return normalized


def validate_effective_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    permissions = profile["permissions"]
    for field_name, controls in ALLOWLIST_DEPENDENCIES.items():
        enabled = sorted(code for code in controls if permissions.get(code))
        if enabled and not profile[field_name]:
            errors.append(f"{field_name} 为空，无法启用: {', '.join(enabled)}")
    return errors


def build_effective_policy(profile: dict[str, Any]) -> dict[str, Any]:
    errors = validate_effective_profile(profile)
    permissions = profile["permissions"]
    return {
        **profile,
        "valid": not errors,
        "validation_errors": errors,
        "guacamole": {
            "disable_copy": not permissions["copy_remote_to_local"],
            "disable_paste": not permissions["paste_local_to_remote"],
            "disable_upload": not permissions["browser_upload"],
            "disable_download": not permissions["browser_download"],
            "enable_printing": permissions["printing"],
            "enable_audio": permissions["audio_output"],
            "enable_audio_input": permissions["audio_input"],
        },
        "vscode": {
            "allowed_extensions": list(profile["allowed_extensions"]),
            "default_workspace_template": profile["default_workspace_template"],
        },
        "applocker": {
            "allowed_shells": list(profile["allowed_shells"]),
            "allowed_tools": list(profile["allowed_tools"]),
            "allowed_debuggers": list(profile["allowed_debuggers"]),
        },
        "firewall": {"allowed_network_targets": list(profile["allowed_network_targets"])},
        "locked_baseline": [dict(item) for item in LOCKED_BASELINE],
    }


def profile_from_row(row: dict[str, Any], *, prefix: str = "") -> dict[str, Any]:
    def field(name: str):
        return row.get(f"{prefix}{name}")

    payload = {
        "profile_key": field("profile_key"),
        "display_name": field("display_name"),
        "description": field("description"),
        "policy_version": field("policy_version"),
        "is_active": bool(field("is_active")),
        "permissions": field("permissions_json"),
        "allowed_shells": field("allowed_shells_json"),
        "allowed_tools": field("allowed_tools_json"),
        "allowed_debuggers": field("allowed_debuggers_json"),
        "allowed_extensions": field("allowed_extensions_json"),
        "allowed_network_targets": field("allowed_network_targets_json"),
        "user_data_root": field("user_data_root"),
        "extensions_root": field("extensions_root"),
        "default_workspace_template": field("default_workspace_template"),
    }
    try:
        profile = normalize_profile_document(payload)
        profile.update(
            {
                "id": int(field("id")),
                "revision": int(field("revision") or 1),
                "created_at": field("created_at"),
                "updated_at": field("updated_at"),
            }
        )
        return profile
    except VscodePolicyError:
        raise
    except (TypeError, ValueError, UnicodeError) as exc:
        raise VscodePolicyError("数据库中的 VSCode 控制策略格式无效") from exc


def validate_restricted_arguments(arguments: str, *, allow_user_id: bool = False) -> str:
    normalized = str(arguments or "").strip()
    if any(char in normalized for char in _DANGEROUS_ARGUMENT_CHARS):
        raise VscodePolicyError("RemoteApp 参数包含危险 shell 字符")
    placeholders = _UNKNOWN_PLACEHOLDER_RE.findall(normalized)
    allowed = {"{user_id}"} if allow_user_id else set()
    unknown = sorted(set(placeholders) - allowed)
    if unknown:
        raise VscodePolicyError(f"RemoteApp 参数包含未知占位符: {', '.join(unknown)}")
    if not allow_user_id and ("{" in normalized or "}" in normalized):
        raise VscodePolicyError("RemoteApp 参数不允许占位符")
    return normalized


def build_vscode_arguments(profile: dict[str, Any], user_id: int) -> str:
    effective = build_effective_policy(profile)
    if not profile.get("is_active"):
        raise VscodePolicyError("VSCode 控制策略未启用")
    if not effective["valid"]:
        raise VscodePolicyError("；".join(effective["validation_errors"]))
    user_data_path = str(PureWindowsPath(profile["user_data_root"]) / str(user_id))
    extensions_path = str(PureWindowsPath(profile["extensions_root"]) / str(user_id))
    workspace = profile["default_workspace_template"]
    return (
        f'--user-data-dir="{user_data_path}" '
        f'--extensions-dir="{extensions_path}" '
        f'--disable-gpu --disable-workspace-trust "{workspace}"'
    )


@dataclass
class VscodePolicyService:
    db: Any

    _SELECT_COLUMNS = """
        id, profile_key, display_name, description, policy_version, is_active, revision,
        permissions_json, allowed_shells_json, allowed_tools_json, allowed_debuggers_json,
        allowed_extensions_json, allowed_network_targets_json,
        user_data_root, extensions_root, default_workspace_template,
        created_at, updated_at
    """

    def list_profiles(self) -> list[dict[str, Any]]:
        rows = self.db.execute_query(
            f"SELECT {self._SELECT_COLUMNS} FROM vscode_control_profile ORDER BY profile_key"
        )
        return [build_effective_policy(profile_from_row(row)) for row in rows]

    def get_profile(self, profile_id: int, *, conn=None) -> dict[str, Any] | None:
        row = self.db.execute_query(
            f"SELECT {self._SELECT_COLUMNS} FROM vscode_control_profile WHERE id = %(id)s LIMIT 1",
            {"id": profile_id},
            fetch_one=True,
            conn=conn,
        )
        return build_effective_policy(profile_from_row(row)) if row else None

    def get_bindable_profile(self, profile_id: int, *, conn=None) -> dict[str, Any]:
        profile = self.get_profile(profile_id, conn=conn)
        if not profile:
            raise VscodePolicyError("VSCode 控制策略不存在")
        if not profile["is_active"]:
            raise VscodePolicyError("VSCode 控制策略未启用")
        if not profile["valid"]:
            raise VscodePolicyError("；".join(profile["validation_errors"]))
        return profile

    def create_profile(self, payload: dict[str, Any], *, conn=None) -> dict[str, Any]:
        normalized = normalize_profile_document(payload, default_permissions=True)
        effective = build_effective_policy(normalized)
        if normalized["is_active"] and not effective["valid"]:
            raise VscodePolicyError("；".join(effective["validation_errors"]))
        duplicate = self.db.execute_query(
            "SELECT id FROM vscode_control_profile WHERE profile_key = %(profile_key)s LIMIT 1",
            {"profile_key": normalized["profile_key"]},
            fetch_one=True,
            conn=conn,
        )
        if duplicate:
            raise VscodePolicyError("profile_key 已存在")
        self.db.execute_update(
            """
            INSERT INTO vscode_control_profile (
                profile_key, display_name, description, policy_version, is_active,
                permissions_json, allowed_shells_json, allowed_tools_json, allowed_debuggers_json,
                allowed_extensions_json, allowed_network_targets_json,
                user_data_root, extensions_root, default_workspace_template
            ) VALUES (
                %(profile_key)s, %(display_name)s, %(description)s, %(policy_version)s, %(is_active)s,
                %(permissions_json)s, %(allowed_shells_json)s, %(allowed_tools_json)s, %(allowed_debuggers_json)s,
                %(allowed_extensions_json)s, %(allowed_network_targets_json)s,
                %(user_data_root)s, %(extensions_root)s, %(default_workspace_template)s
            )
            """,
            self._db_payload(normalized),
            conn=conn,
        )
        row = self.db.execute_query(
            f"SELECT {self._SELECT_COLUMNS} FROM vscode_control_profile WHERE profile_key = %(profile_key)s LIMIT 1",
            {"profile_key": normalized["profile_key"]},
            fetch_one=True,
            conn=conn,
        )
        return build_effective_policy(profile_from_row(row))

    def update_profile(self, profile_id: int, payload: dict[str, Any], *, conn=None) -> dict[str, Any]:
        current = self.get_profile(profile_id, conn=conn)
        if not current:
            raise VscodePolicyError("VSCode 控制策略不存在")
        merged = {
            key: payload.get(key, current[key])
            for key in (
                "profile_key", "display_name", "description", "policy_version", "is_active",
                "permissions", "allowed_shells", "allowed_tools", "allowed_debuggers",
                "allowed_extensions", "allowed_network_targets", "user_data_root",
                "extensions_root", "default_workspace_template",
            )
        }
        normalized = normalize_profile_document(merged)
        effective = build_effective_policy(normalized)
        if normalized["is_active"] and not effective["valid"]:
            raise VscodePolicyError("；".join(effective["validation_errors"]))
        duplicate = self.db.execute_query(
            """
            SELECT id FROM vscode_control_profile
            WHERE profile_key = %(profile_key)s AND id <> %(id)s
            LIMIT 1
            """,
            {"profile_key": normalized["profile_key"], "id": profile_id},
            fetch_one=True,
            conn=conn,
        )
        if duplicate:
            raise VscodePolicyError("profile_key 已存在")
        self.db.execute_update(
            """
            UPDATE vscode_control_profile
            SET profile_key = %(profile_key)s,
                display_name = %(display_name)s,
                description = %(description)s,
                policy_version = %(policy_version)s,
                is_active = %(is_active)s,
                permissions_json = %(permissions_json)s,
                allowed_shells_json = %(allowed_shells_json)s,
                allowed_tools_json = %(allowed_tools_json)s,
                allowed_debuggers_json = %(allowed_debuggers_json)s,
                allowed_extensions_json = %(allowed_extensions_json)s,
                allowed_network_targets_json = %(allowed_network_targets_json)s,
                user_data_root = %(user_data_root)s,
                extensions_root = %(extensions_root)s,
                default_workspace_template = %(default_workspace_template)s,
                revision = revision + 1
            WHERE id = %(id)s
            """,
            {**self._db_payload(normalized), "id": profile_id},
            conn=conn,
        )
        return self.get_profile(profile_id, conn=conn)

    def delete_profile(self, profile_id: int, *, conn=None) -> None:
        bound = self.db.execute_query(
            "SELECT id FROM remote_app WHERE vscode_control_profile_id = %(id)s LIMIT 1",
            {"id": profile_id},
            fetch_one=True,
            conn=conn,
        )
        if bound:
            raise VscodePolicyError("策略仍被应用绑定，不能删除")
        deleted = self.db.execute_update(
            "DELETE FROM vscode_control_profile WHERE id = %(id)s",
            {"id": profile_id},
            conn=conn,
        )
        if deleted <= 0:
            raise VscodePolicyError("VSCode 控制策略不存在")

    @staticmethod
    def _db_payload(profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "profile_key": profile["profile_key"],
            "display_name": profile["display_name"],
            "description": profile["description"],
            "policy_version": profile["policy_version"],
            "is_active": 1 if profile["is_active"] else 0,
            "permissions_json": json.dumps(profile["permissions"], ensure_ascii=False),
            "allowed_shells_json": json.dumps(profile["allowed_shells"], ensure_ascii=False),
            "allowed_tools_json": json.dumps(profile["allowed_tools"], ensure_ascii=False),
            "allowed_debuggers_json": json.dumps(profile["allowed_debuggers"], ensure_ascii=False),
            "allowed_extensions_json": json.dumps(profile["allowed_extensions"], ensure_ascii=False),
            "allowed_network_targets_json": json.dumps(profile["allowed_network_targets"], ensure_ascii=False),
            "user_data_root": profile["user_data_root"],
            "extensions_root": profile["extensions_root"],
            "default_workspace_template": profile["default_workspace_template"],
        }
