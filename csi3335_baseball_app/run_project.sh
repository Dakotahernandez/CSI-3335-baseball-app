#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"
APP_DIR="$PROJECT_ROOT"
VENV_DIR="$PROJECT_ROOT/.venv"
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
USER_SQL="$PROJECT_ROOT/user.sql"

declare -a BASEBALL_SQL_SEARCH_PATHS=(
    "$PARENT_ROOT/MYSQL/baseball.sql"
    "$PROJECT_ROOT/../../MYSQL/baseball.sql"
    "$HOME/MYSQL/baseball.sql"
)

declare -a REQUIRED_TABLES=(
    "teams"
    "people"
    "batting"
)

BASEBALL_SQL_FROM_ENV=0
BASEBALL_SQL_OVERRIDE="${BASEBALL_SQL:-}"
if [[ -n "$BASEBALL_SQL_OVERRIDE" ]]; then
    BASEBALL_SQL_FROM_ENV=1
    BASEBALL_SQL="$BASEBALL_SQL_OVERRIDE"
else
    BASEBALL_SQL=""
    for candidate in "${BASEBALL_SQL_SEARCH_PATHS[@]}"; do
        if [[ -n "$candidate" && -f "$candidate" ]]; then
            BASEBALL_SQL="$candidate"
            break
        fi
    done
    if [[ -z "$BASEBALL_SQL" ]]; then
        BASEBALL_SQL="${BASEBALL_SQL_SEARCH_PATHS[0]}"
    fi
fi

DB_CONTAINER_NAME="${DB_CONTAINER_NAME:-csi3335_baseball_db}"
DB_DATA_DIR="${DB_DATA_DIR:-$PROJECT_ROOT/.mariadb-data}"
DB_PORT="${DB_PORT:-3306}"
MYSQL_DATABASE="${MYSQL_DATABASE:-baseball}"
MYSQL_USER="${MYSQL_USER:-web}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-mypass}"
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-rootpass}"

FLASK_HOST="${FLASK_HOST:-127.0.0.1}"
FLASK_PORT="${FLASK_PORT:-5000}"
FLASK_PORT_ATTEMPTS="${FLASK_PORT_ATTEMPTS:-10}"

DB_ALREADY_RUNNING=0
CLEANUP_COMPLETE=0
FLASK_PID=""

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

abort() {
    echo "Error: $*" >&2
    exit 1
}

cleanup() {
    if [[ $CLEANUP_COMPLETE -eq 1 ]]; then
        return
    fi
    CLEANUP_COMPLETE=1

    echo ""
    log "Stopping services..."

    if [[ -n "${FLASK_PID}" ]] && kill -0 "${FLASK_PID}" 2>/dev/null; then
        kill "${FLASK_PID}" >/dev/null 2>&1 || true
        wait "${FLASK_PID}" 2>/dev/null || true
    fi

    if [[ $DB_ALREADY_RUNNING -eq 1 ]]; then
        log "Database container ${DB_CONTAINER_NAME} was already running; leaving it untouched."
        return
    fi

    if docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER_NAME}$"; then
        docker stop "${DB_CONTAINER_NAME}" >/dev/null 2>&1 || true
    fi

    if docker ps -a --format '{{.Names}}' | grep -q "^${DB_CONTAINER_NAME}$"; then
        docker rm "${DB_CONTAINER_NAME}" >/dev/null 2>&1 || true
    fi
}

trap cleanup INT TERM EXIT

check_prereqs() {
    command -v docker >/dev/null 2>&1 || abort "docker is required but not found in PATH."
    command -v python3 >/dev/null 2>&1 || abort "python3 is required but not found in PATH."
}

ensure_venv() {
    if [[ ! -d "${VENV_DIR}" ]]; then
        log "Creating virtual environment in ${VENV_DIR}"
        python3 -m venv "${VENV_DIR}"
    fi

    # shellcheck disable=SC1090
    source "${VENV_DIR}/bin/activate"

    log "Installing Python dependencies (skipping if already satisfied)..."
    python -m pip install --upgrade --quiet pip
    python -m pip install --quiet -r "${REQUIREMENTS_FILE}"
}

is_port_in_use() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        if lsof -iTCP:"${port}" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
            return 0
        fi
    else
        python3 - <<'PY' "$port"
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.5)
    result = sock.connect_ex(("127.0.0.1", port))
sys.exit(0 if result == 0 else 1)
PY
        if [[ $? -eq 0 ]]; then
            return 0
        fi
    fi
    return 1
}

choose_flask_port() {
    local start_port="$1"
    local max_attempts="$2"
    local attempt=0
    local port="$start_port"

    while (( attempt < max_attempts )); do
        if ! is_port_in_use "$port"; then
            echo "$port"
            return 0
        fi
        port=$((port + 1))
        attempt=$((attempt + 1))
    done

    return 1
}

wait_for_db() {
    log "Waiting for MariaDB to accept connections..."
    local attempt=0
    until docker exec "${DB_CONTAINER_NAME}" mariadb-admin \
        --host=127.0.0.1 \
        --user=root \
        --password="${MYSQL_ROOT_PASSWORD}" \
        ping --silent >/dev/null 2>&1; do
        sleep 2
        attempt=$((attempt + 1))
        if (( attempt > 30 )); then
            abort "MariaDB did not become ready in time."
        fi
    done
}

start_db_container() {
    mkdir -p "${DB_DATA_DIR}"

    if docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER_NAME}$"; then
        DB_ALREADY_RUNNING=1
        log "Using existing running database container ${DB_CONTAINER_NAME}."
    elif docker ps -a --format '{{.Names}}' | grep -q "^${DB_CONTAINER_NAME}$"; then
        log "Starting stopped database container ${DB_CONTAINER_NAME}."
        docker start "${DB_CONTAINER_NAME}" >/dev/null
    else
        log "Creating new MariaDB container ${DB_CONTAINER_NAME}."
        docker run -d \
            --name "${DB_CONTAINER_NAME}" \
            -e "MARIADB_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}" \
            -e "MARIADB_DATABASE=${MYSQL_DATABASE}" \
            -e "MARIADB_USER=${MYSQL_USER}" \
            -e "MARIADB_PASSWORD=${MYSQL_PASSWORD}" \
            -p "${DB_PORT}:3306" \
            -v "${DB_DATA_DIR}:/var/lib/mysql" \
            mariadb:11.4 >/dev/null
    fi

    wait_for_db
}

import_sql_file() {
    local src_path="$1"
    local label="$2"
    local container_path="/tmp/${label}"

    docker cp "${src_path}" "${DB_CONTAINER_NAME}:${container_path}"
    docker exec "${DB_CONTAINER_NAME}" sh -c \
        "mariadb -uroot -p${MYSQL_ROOT_PASSWORD} ${MYSQL_DATABASE} < ${container_path}"
    docker exec "${DB_CONTAINER_NAME}" rm -f "${container_path}" >/dev/null 2>&1 || true
}

seed_database_if_needed() {
    local table_count
    table_count="$(docker exec "${DB_CONTAINER_NAME}" mariadb -N -uroot -p"${MYSQL_ROOT_PASSWORD}" \
        -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${MYSQL_DATABASE}';" || echo 0)"

    local -a missing_tables=()
    local required_table
    for required_table in "${REQUIRED_TABLES[@]}"; do
        local exists
        exists="$(docker exec "${DB_CONTAINER_NAME}" mariadb -N -uroot -p"${MYSQL_ROOT_PASSWORD}" \
            -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${MYSQL_DATABASE}' AND table_name='${required_table}';" 2>/dev/null || echo 0)"
        if ! [[ "${exists}" =~ ^[0-9]+$ ]] || [[ "${exists}" -eq 0 ]]; then
            missing_tables+=("${required_table}")
        fi
    done

    if (( ${#missing_tables[@]} > 0 )); then
        if [[ -f "${BASEBALL_SQL}" ]]; then
            log "Loading baseball dataset from ${BASEBALL_SQL} (missing tables: ${missing_tables[*]})..."
            import_sql_file "${BASEBALL_SQL}" "baseball.sql"
            table_count="$(docker exec "${DB_CONTAINER_NAME}" mariadb -N -uroot -p"${MYSQL_ROOT_PASSWORD}" \
                -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${MYSQL_DATABASE}';" || echo 0)"
        else
            if [[ $BASEBALL_SQL_FROM_ENV -eq 1 ]]; then
                log "baseball.sql not found at ${BASEBALL_SQL} (specified via BASEBALL_SQL)."
            else
                local joined_paths=""
                local candidate_path
                for candidate_path in "${BASEBALL_SQL_SEARCH_PATHS[@]}"; do
                    if [[ -n "$joined_paths" ]]; then
                        joined_paths+=", "
                    fi
                    joined_paths+="$candidate_path"
                done
                log "baseball.sql not found. Checked paths: ${joined_paths}"
            fi
            log "Provide BASEBALL_SQL=/path/to/baseball.sql to load the dataset automatically."
        fi
    else
        log "Baseball schema already present (${table_count} tables)."
    fi

    if [[ -f "${USER_SQL}" ]]; then
        log "Applying user.sql to refresh application users table."
        import_sql_file "${USER_SQL}" "user.sql"
    else
        log "user.sql not found at ${USER_SQL}; skipping user table refresh."
    fi
}

start_flask() {
    export FLASK_APP="run.py"

    local effective_port
    if ! effective_port="$(choose_flask_port "${FLASK_PORT}" "${FLASK_PORT_ATTEMPTS}")"; then
        abort "Unable to find a free port starting at ${FLASK_PORT} (checked ${FLASK_PORT_ATTEMPTS} ports)."
    fi
    if [[ "${effective_port}" != "${FLASK_PORT}" ]]; then
        log "Port ${FLASK_PORT} is busy; using ${effective_port} instead."
    fi

    export FLASK_RUN_PORT="${effective_port}"

    log "Starting Flask development server at http://${FLASK_HOST}:${effective_port}/"
    (
        cd "${APP_DIR}"
        python -m flask run --host="${FLASK_HOST}" --port="${effective_port}"
    ) &
    FLASK_PID=$!
    wait "${FLASK_PID}"
}

main() {
    check_prereqs
    ensure_venv
    start_db_container
    seed_database_if_needed
    start_flask
}

main "$@"
