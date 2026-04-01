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

# ── 加载 .env ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

read_env_value() {
    local key="$1"
    grep -E "^${key}=" "$ENV_FILE" | cut -d'=' -f2- || true
}

if [[ -f "$ENV_FILE" ]]; then
    # 只提取需要的变量，避免 export 污染
    MYSQL_ROOT_PASSWORD=$(read_env_value 'MYSQL_ROOT_PASSWORD')
    if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
        MYSQL_ROOT_PASSWORD=$(read_env_value 'GUAC_DB_ROOT_PASSWORD')
    fi
else
    echo "ERROR: 找不到 .env 文件: $ENV_FILE"
    exit 1
fi

if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
    echo "ERROR: .env 中未设置 MYSQL_ROOT_PASSWORD 或 GUAC_DB_ROOT_PASSWORD"
    exit 1
fi

# ── 常量 ───────────────────────────────────────────────────
MYSQL_CONTAINER="nercar-portal-guac-sql"
MYSQL_VOLUME="guacamole_mysql_data"
DRIVE_VOLUME="guacamole_guacd_drive"
COMPOSE_PROJECT="nercar-portal"

# ── 函数 ───────────────────────────────────────────────────

check_container_running() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${MYSQL_CONTAINER}$"; then
        echo "ERROR: MySQL 容器 ${MYSQL_CONTAINER} 未运行"
        echo "  请先启动: cd deploy && docker compose up -d"
        exit 1
    fi
}

check_volume_exists() {
    local vol="$1"
    if ! docker volume inspect "$vol" &>/dev/null; then
        echo "WARNING: 卷 ${vol} 不存在"
        return 1
    fi
    return 0
}

do_export() {
    local backup_dir="${1:-${SCRIPT_DIR}/backups/$(date +%Y%m%d_%H%M%S)}"
    mkdir -p "$backup_dir"

    echo "╔══════════════════════════════════════════════╗"
    echo "║  Guacamole Portal — 数据导出                ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    echo "目标目录: $backup_dir"
    echo ""

    # ── MySQL dump ─────────────────────────────────────
    echo "▶ [1/2] 导出 MySQL 数据库..."
    check_container_running

    docker exec "$MYSQL_CONTAINER" \
        mysqldump -uroot -p"${MYSQL_ROOT_PASSWORD}" \
        --default-character-set=utf8mb4 \
        --hex-blob \
        --single-transaction \
        --routines --triggers --events \
        --databases guacamole_portal_db guacamole_db \
        > "${backup_dir}/portal_dump.sql" 2>/dev/null

    local dump_size
    dump_size=$(wc -c < "${backup_dir}/portal_dump.sql" 2>/dev/null || echo 0)

    if [[ "$dump_size" -lt 100 ]]; then
        echo "  ✗ MySQL dump 异常 (${dump_size} bytes)，请检查容器日志"
        rm -f "${backup_dir}/portal_dump.sql"
        exit 1
    fi
    echo "  ✓ portal_dump.sql ($(numfmt --to=iec "$dump_size" 2>/dev/null || echo "${dump_size} bytes"))"

    # ── Drive 文件 ─────────────────────────────────────
    echo "▶ [2/2] 导出 Drive 文件..."

    if check_volume_exists "$DRIVE_VOLUME"; then
        docker run --rm \
            -v "${DRIVE_VOLUME}:/data:ro" \
            -v "${backup_dir}:/backup" \
            alpine \
            tar czf /backup/drive_files.tar.gz -C /data .

        local tar_size
        tar_size=$(wc -c < "${backup_dir}/drive_files.tar.gz" 2>/dev/null || echo 0)
        echo "  ✓ drive_files.tar.gz ($(numfmt --to=iec "$tar_size" 2>/dev/null || echo "${tar_size} bytes"))"
    else
        echo "  ⊘ Drive 卷不存在，跳过"
    fi

    echo ""
    echo "═══════════════════════════════════════════════"
    echo "  备份完成: $backup_dir"
    echo "═══════════════════════════════════════════════"
    ls -lh "$backup_dir"/
}

do_import() {
    local backup_dir="$1"

    if [[ ! -d "$backup_dir" ]]; then
        echo "ERROR: 备份目录不存在: $backup_dir"
        exit 1
    fi

    echo "╔══════════════════════════════════════════════╗"
    echo "║  Guacamole Portal — 数据恢复                ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    echo "来源目录: $backup_dir"
    echo ""
    echo "⚠️  这将覆盖当前数据库内容！"
    read -rp "确认恢复? [y/N] " confirm
    if [[ "${confirm,,}" != "y" ]]; then
        echo "已取消"
        exit 0
    fi

    # ── MySQL 恢复 ─────────────────────────────────────
    if [[ -f "${backup_dir}/portal_dump.sql" ]]; then
        echo "▶ [1/2] 恢复 MySQL 数据库..."
        check_container_running

        docker exec -i "$MYSQL_CONTAINER" \
            mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" \
            --default-character-set=utf8mb4 \
            < "${backup_dir}/portal_dump.sql"

        echo "  ✓ MySQL 数据库已恢复"
    else
        echo "  ⊘ 未找到 portal_dump.sql，跳过 MySQL 恢复"
    fi

    # ── Drive 恢复 ─────────────────────────────────────
    if [[ -f "${backup_dir}/drive_files.tar.gz" ]]; then
        echo "▶ [2/2] 恢复 Drive 文件..."

        docker run --rm \
            -v "${DRIVE_VOLUME}:/data" \
            -v "$(cd "$backup_dir" && pwd):/backup:ro" \
            alpine \
            sh -c "cd /data && tar xzf /backup/drive_files.tar.gz"

        echo "  ✓ Drive 文件已恢复"
    else
        echo "  ⊘ 未找到 drive_files.tar.gz，跳过 Drive 恢复"
    fi

    echo ""
    echo "═══════════════════════════════════════════════"
    echo "  恢复完成"
    echo "═══════════════════════════════════════════════"
}

do_status() {
    echo "╔══════════════════════════════════════════════╗"
    echo "║  Guacamole Portal — 卷状态                  ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""

    for vol in "$MYSQL_VOLUME" "$DRIVE_VOLUME"; do
        echo "▶ ${vol}"
        if check_volume_exists "$vol"; then
            docker volume inspect "$vol" --format '  Driver:     {{.Driver}}'
            docker volume inspect "$vol" --format '  Mountpoint: {{.Mountpoint}}'

            # 计算数据大小
            local size
            size=$(docker run --rm -v "${vol}:/data:ro" alpine du -sh /data 2>/dev/null | cut -f1)
            echo "  Size:       ${size:-unknown}"
        fi
        echo ""
    done

    # 容器状态
    echo "▶ 容器状态"
    docker ps --filter "label=com.docker.compose.project=${COMPOSE_PROJECT}" \
        --format "  {{.Names}}\t{{.Status}}" 2>/dev/null || \
    docker ps --filter "name=nercar-portal" \
        --format "  {{.Names}}\t{{.Status}}" 2>/dev/null || \
    echo "  (无法获取容器状态)"
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
