#!/usr/bin/env bash
# Guacamole RemoteApp Portal — 数据备份/恢复脚本
# 用法:
#   ./backup.sh export [目标目录]   — 导出 MySQL dump + drive 文件
#   ./backup.sh import <备份目录>   — 从备份恢复
#   ./backup.sh status              — 显示卷状态和数据大小
#
# 默认备份到 ./backups/<时间戳>/
# 需在 deploy/ 目录下执行 (或同级 .env 文件所在目录)

set -euo pipefail

# Git Bash (MSYS2) 会把 /path 转换成 D:/Program Files/Git/path，
# 导致 docker run -v 挂载路径出错。全局禁用路径转换。
export MSYS_NO_PATHCONV=1

# ── 路径 / 环境 ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
UPLOAD_BACKUP_IMAGE="alpine"

read_env_value() {
    local key="$1"
    grep -E "^${key}=" "$ENV_FILE" | cut -d'=' -f2- || true
}

kv() {
    local key="$1"
    local value="${2:-}"
    printf '%s=%q' "$key" "$value"
}

log_line() {
    local level="$1"
    local event="$2"
    shift 2
    printf '%s level=%s instance=%s event=%s' \
        "$(date '+%Y-%m-%dT%H:%M:%S%z')" \
        "$level" \
        "$PORTAL_INSTANCE_ID" \
        "$event"
    for field in "$@"; do
        printf ' %s' "$field"
    done
    printf '\n'
}

compose_cmd() {
    docker compose \
        --env-file "$ENV_FILE" \
        -f "$COMPOSE_FILE" \
        --project-name "$PORTAL_INSTANCE_ID" \
        "$@"
}

if [[ -f "$ENV_FILE" ]]; then
    MYSQL_ROOT_PASSWORD="$(read_env_value 'MYSQL_ROOT_PASSWORD')"
    if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
        MYSQL_ROOT_PASSWORD="$(read_env_value 'GUAC_DB_ROOT_PASSWORD')"
    fi
    PORTAL_INSTANCE_ID="$(read_env_value 'PORTAL_INSTANCE_ID')"
else
    echo "ERROR: 找不到 .env 文件: $ENV_FILE"
    exit 1
fi

PORTAL_INSTANCE_ID="${PORTAL_INSTANCE_ID:-nercar-portal}"

if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
    echo "ERROR: .env 中未设置 MYSQL_ROOT_PASSWORD 或 GUAC_DB_ROOT_PASSWORD"
    exit 1
fi

# ── Compose / Mount 解析 ────────────────────────────────────

resolve_service_container_id() {
    local service="$1"
    compose_cmd ps -q "$service" 2>/dev/null | tr -d '\r'
}

require_service_container_id() {
    local service="$1"
    local container_id
    container_id="$(resolve_service_container_id "$service")"
    if [[ -z "$container_id" ]]; then
        echo "ERROR: 服务 ${service} 未运行"
        echo "  请先启动: cd deploy && docker compose up -d"
        exit 1
    fi
    printf '%s' "$container_id"
}

inspect_mount_binding() {
    local container_id="$1"
    local destination="$2"
    docker inspect "$container_id" \
        --format "{{range .Mounts}}{{if eq .Destination \"${destination}\"}}{{.Type}}|{{.Name}}|{{.Source}}{{end}}{{end}}" \
        2>/dev/null | tr -d '\r'
}

resolve_mount_binding() {
    local service="$1"
    local destination="$2"
    local container_id
    local mount_info
    local mount_type
    local mount_name
    local mount_source
    local mount_spec
    local mount_display

    container_id="$(resolve_service_container_id "$service")"
    if [[ -z "$container_id" ]]; then
        return 1
    fi

    mount_info="$(inspect_mount_binding "$container_id" "$destination")"
    if [[ -z "$mount_info" ]]; then
        return 1
    fi

    IFS='|' read -r mount_type mount_name mount_source <<< "$mount_info"
    case "$mount_type" in
        volume)
            mount_spec="$mount_name"
            mount_display="$mount_name"
            ;;
        bind)
            mount_spec="$mount_source"
            mount_display="$mount_source"
            ;;
        *)
            return 1
            ;;
    esac

    printf '%s|%s|%s|%s' "$mount_type" "$mount_spec" "$mount_display" "$mount_source"
}

resolve_drive_mount_binding() {
    local service
    local mount_info

    for service in portal-backend guacd nginx; do
        mount_info="$(resolve_mount_binding "$service" "/drive" || true)"
        if [[ -n "$mount_info" ]]; then
            printf '%s|%s' "$service" "$mount_info"
            return 0
        fi
    done
    return 1
}

mount_size() {
    local mount_spec="$1"
    docker run --rm -v "${mount_spec}:/data:ro" "$UPLOAD_BACKUP_IMAGE" \
        du -sh /data 2>/dev/null | cut -f1
}

print_mount_status() {
    local title="$1"
    local service="$2"
    local destination="$3"
    local mount_info
    local mount_type
    local mount_spec
    local mount_display
    local raw_source
    local size

    echo "▶ ${title}"
    mount_info="$(resolve_mount_binding "$service" "$destination" || true)"
    if [[ -z "$mount_info" ]]; then
        echo "  状态:       服务未运行或挂载未解析"
        echo ""
        return
    fi

    IFS='|' read -r mount_type mount_spec mount_display raw_source <<< "$mount_info"
    echo "  Type:       ${mount_type}"
    echo "  Source:     ${mount_display}"
    if [[ "$mount_type" == "bind" ]]; then
        echo "  RawSource:  ${raw_source}"
    fi
    size="$(mount_size "$mount_spec" || true)"
    echo "  Size:       ${size:-unknown}"
    echo ""
}

print_drive_mount_status() {
    local mount_info
    local mount_service
    local mount_type
    local mount_spec
    local mount_display
    local raw_source
    local size

    echo "▶ Drive 数据挂载"
    mount_info="$(resolve_drive_mount_binding || true)"
    if [[ -z "$mount_info" ]]; then
        echo "  状态:       服务未运行或挂载未解析"
        echo ""
        return
    fi

    IFS='|' read -r mount_service mount_type mount_spec mount_display raw_source <<< "$mount_info"
    echo "  Service:    ${mount_service}"
    echo "  Type:       ${mount_type}"
    echo "  Source:     ${mount_display}"
    if [[ "$mount_type" == "bind" ]]; then
        echo "  RawSource:  ${raw_source}"
    fi
    size="$(mount_size "$mount_spec" || true)"
    echo "  Size:       ${size:-unknown}"
    echo ""
}

# ── 业务动作 ────────────────────────────────────────────────

do_export() {
    local backup_dir="${1:-${SCRIPT_DIR}/backups/$(date +%Y%m%d_%H%M%S)}"
    local drive_mount_info
    local drive_mount_service
    local drive_mount_type
    local drive_mount_spec
    local drive_mount_display
    local drive_mount_source
    local dump_size
    local tar_size

    mkdir -p "$backup_dir"

    log_line INFO backup_export_started \
        "$(kv backup_dir "$backup_dir")"

    echo "╔══════════════════════════════════════════════╗"
    echo "║  Guacamole Portal — 数据导出                ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    echo "实例标识: $PORTAL_INSTANCE_ID"
    echo "目标目录: $backup_dir"
    echo ""

    echo "▶ [1/2] 导出 MySQL 数据库..."
    require_service_container_id "guac-sql" >/dev/null

    compose_cmd exec -T guac-sql \
        mysqldump -uroot -p"${MYSQL_ROOT_PASSWORD}" \
        --default-character-set=utf8mb4 \
        --hex-blob \
        --single-transaction \
        --routines --triggers --events \
        --databases guacamole_portal_db guacamole_db \
        > "${backup_dir}/portal_dump.sql" 2>/dev/null

    dump_size="$(wc -c < "${backup_dir}/portal_dump.sql" 2>/dev/null || echo 0)"
    if [[ "$dump_size" -lt 100 ]]; then
        echo "  ✗ MySQL dump 异常 (${dump_size} bytes)，请检查容器日志"
        rm -f "${backup_dir}/portal_dump.sql"
        exit 1
    fi
    echo "  ✓ portal_dump.sql ($(numfmt --to=iec "$dump_size" 2>/dev/null || echo "${dump_size} bytes"))"

    echo "▶ [2/2] 导出 Drive 文件..."
    drive_mount_info="$(resolve_drive_mount_binding || true)"
    if [[ -z "$drive_mount_info" ]]; then
        echo "  ⊘ Drive 挂载未解析，跳过"
        log_line WARNING backup_export_drive_skipped \
            "$(kv reason "drive-mount-unavailable")"
    else
        IFS='|' read -r drive_mount_service drive_mount_type drive_mount_spec drive_mount_display drive_mount_source <<< "$drive_mount_info"
        log_line INFO backup_export_drive_source \
            "$(kv service "$drive_mount_service")" \
            "$(kv mount_type "$drive_mount_type")" \
            "$(kv mount_source "$drive_mount_display")"
        docker run --rm \
            -v "${drive_mount_spec}:/data:ro" \
            -v "${backup_dir}:/backup" \
            "$UPLOAD_BACKUP_IMAGE" \
            tar czf /backup/drive_files.tar.gz -C /data .

        tar_size="$(wc -c < "${backup_dir}/drive_files.tar.gz" 2>/dev/null || echo 0)"
        echo "  ✓ drive_files.tar.gz ($(numfmt --to=iec "$tar_size" 2>/dev/null || echo "${tar_size} bytes"))"
    fi

    echo ""
    echo "═══════════════════════════════════════════════"
    echo "  备份完成: $backup_dir"
    echo "═══════════════════════════════════════════════"
    ls -lh "$backup_dir"/

    log_line INFO backup_export_completed \
        "$(kv backup_dir "$backup_dir")" \
        "$(kv dump_bytes "$dump_size")"
}

do_import() {
    local backup_dir="$1"
    local drive_mount_info
    local drive_mount_service
    local drive_mount_type
    local drive_mount_spec
    local drive_mount_display
    local drive_mount_source

    if [[ ! -d "$backup_dir" ]]; then
        echo "ERROR: 备份目录不存在: $backup_dir"
        exit 1
    fi

    log_line INFO backup_import_started \
        "$(kv backup_dir "$backup_dir")"

    echo "╔══════════════════════════════════════════════╗"
    echo "║  Guacamole Portal — 数据恢复                ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    echo "实例标识: $PORTAL_INSTANCE_ID"
    echo "来源目录: $backup_dir"
    echo ""
    echo "⚠️  这将覆盖当前数据库内容！"
    read -rp "确认恢复? [y/N] " confirm
    if [[ "${confirm,,}" != "y" ]]; then
        echo "已取消"
        log_line INFO backup_import_cancelled
        exit 0
    fi

    if [[ -f "${backup_dir}/portal_dump.sql" ]]; then
        echo "▶ [1/2] 恢复 MySQL 数据库..."
        require_service_container_id "guac-sql" >/dev/null

        compose_cmd exec -T guac-sql \
            mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" \
            --default-character-set=utf8mb4 \
            < "${backup_dir}/portal_dump.sql"

        echo "  ✓ MySQL 数据库已恢复"
    else
        echo "  ⊘ 未找到 portal_dump.sql，跳过 MySQL 恢复"
    fi

    if [[ -f "${backup_dir}/drive_files.tar.gz" ]]; then
        echo "▶ [2/2] 恢复 Drive 文件..."
        drive_mount_info="$(resolve_drive_mount_binding || true)"
        if [[ -z "$drive_mount_info" ]]; then
            echo "ERROR: Drive 挂载未解析，无法恢复 drive 文件"
            exit 1
        fi

        IFS='|' read -r drive_mount_service drive_mount_type drive_mount_spec drive_mount_display drive_mount_source <<< "$drive_mount_info"
        log_line INFO backup_import_drive_source \
            "$(kv service "$drive_mount_service")" \
            "$(kv mount_type "$drive_mount_type")" \
            "$(kv mount_source "$drive_mount_display")"
        docker run --rm \
            -v "${drive_mount_spec}:/data" \
            -v "$(cd "$backup_dir" && pwd):/backup:ro" \
            "$UPLOAD_BACKUP_IMAGE" \
            sh -c "cd /data && tar xzf /backup/drive_files.tar.gz"

        echo "  ✓ Drive 文件已恢复"
    else
        echo "  ⊘ 未找到 drive_files.tar.gz，跳过 Drive 恢复"
    fi

    echo ""
    echo "═══════════════════════════════════════════════"
    echo "  恢复完成"
    echo "═══════════════════════════════════════════════"

    log_line INFO backup_import_completed \
        "$(kv backup_dir "$backup_dir")"
}

do_status() {
    log_line INFO backup_status_started

    echo "╔══════════════════════════════════════════════╗"
    echo "║  Guacamole Portal — 卷状态                  ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    echo "实例标识: $PORTAL_INSTANCE_ID"
    echo ""

    print_mount_status "MySQL 数据挂载" "guac-sql" "/var/lib/mysql"
    print_drive_mount_status

    echo "▶ 容器状态"
    compose_cmd ps --format "  {{.Service}}\t{{.Status}}" 2>/dev/null || \
        echo "  (无法获取容器状态)"

    log_line INFO backup_status_completed
}

# ── 入口 ───────────────────────────────────────────────────

case "${1:-help}" in
    export)
        do_export "${2:-}"
        ;;
    import)
        if [[ -z "${2:-}" ]]; then
            echo "用法: $0 import <备份目录>"
            echo "示例: $0 import ./backups/20260321_215500"
            exit 1
        fi
        do_import "$2"
        ;;
    status)
        do_status
        ;;
    *)
        echo "Guacamole Portal 数据备份/恢复工具"
        echo ""
        echo "用法:"
        echo "  $0 export [目标目录]   导出 MySQL + Drive 数据"
        echo "  $0 import <备份目录>   从备份恢复数据"
        echo "  $0 status              查看卷状态和数据大小"
        echo ""
        echo "示例:"
        echo "  $0 export                          # 备份到 ./backups/<时间戳>/"
        echo "  $0 export /d/backups/portal        # 备份到指定目录"
        echo "  $0 import ./backups/20260321_215500 # 恢复指定备份"
        ;;
esac
