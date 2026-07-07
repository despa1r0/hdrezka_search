#!/usr/bin/env bash

set -Eeuo pipefail

readonly PROJECT_DIR="/opt/hdrezka_search"
readonly BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
readonly DB_CONTAINER="${DB_CONTAINER:-hdrezka-postgres}"
readonly RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
readonly LOCK_FILE="${XDG_RUNTIME_DIR:-/tmp}/hdrezka-search-backup-${UID}.lock"
CONTAINER_TMP=""
HOST_PARTIAL=""

log() {
    printf '[backup] %s\n' "$*"
}

fail() {
    log "ERROR: $*" >&2
    exit 1
}

cleanup() {
    if [[ -n "${CONTAINER_TMP}" ]]; then
        docker exec "${DB_CONTAINER}" rm -f "${CONTAINER_TMP}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${HOST_PARTIAL}" ]]; then
        rm -f "${HOST_PARTIAL}"
    fi
}

main() {
    local timestamp=""
    local filename=""
    local host_final=""
    local db_health=""

    [[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]] || fail "BACKUP_RETENTION_DAYS must be a non-negative integer"

    for command in docker flock sha256sum; do
        command -v "${command}" >/dev/null || fail "required command is missing: ${command}"
    done

    exec 9>"${LOCK_FILE}"
    flock -n 9 || fail "another database backup is already running"

    db_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${DB_CONTAINER}" 2>/dev/null)" \
        || fail "cannot inspect ${DB_CONTAINER}"
    [[ "${db_health}" == "healthy" ]] || fail "PostgreSQL container is not healthy: ${db_health}"

    install -d -m 700 "${BACKUP_DIR}"

    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    filename="hdrezka_auto_${timestamp}.dump"
    CONTAINER_TMP="/tmp/${filename}.partial"
    HOST_PARTIAL="${BACKUP_DIR}/.${filename}.partial"
    host_final="${BACKUP_DIR}/${filename}"

    trap cleanup EXIT

    log "Creating PostgreSQL dump"
    docker exec "${DB_CONTAINER}" sh -c \
        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "$1"' \
        sh "${CONTAINER_TMP}"

    log "Validating dump catalog"
    docker exec "${DB_CONTAINER}" pg_restore --list "${CONTAINER_TMP}" >/dev/null

    docker cp "${DB_CONTAINER}:${CONTAINER_TMP}" "${HOST_PARTIAL}" >/dev/null
    chmod 600 "${HOST_PARTIAL}"
    mv "${HOST_PARTIAL}" "${host_final}"
    HOST_PARTIAL=""
    sha256sum "${host_final}" > "${host_final}.sha256"
    chmod 600 "${host_final}.sha256"

    log "Removing backups older than ${RETENTION_DAYS} days"
    find "${BACKUP_DIR}" -maxdepth 1 -type f \
        \( -name 'hdrezka_auto_*.dump' -o -name 'hdrezka_auto_*.dump.sha256' \) \
        -mtime "+${RETENTION_DAYS}" -delete

    log "Backup completed: ${host_final}"
}

main "$@"
