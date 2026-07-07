#!/usr/bin/env bash

set -Eeuo pipefail

readonly PROJECT_DIR="/opt/hdrezka_search"
readonly COMPOSE_FILE="${PROJECT_DIR}/docker-compose.prod.yml"
readonly IMAGE_REPOSITORY="ghcr.io/despa1r0/hdrezka_search"
readonly APP_CONTAINER="hdrezka-app"
readonly CANDIDATE_CONTAINER="hdrezka-app-candidate"
readonly GLUETUN_CONTAINER="hdrezka-gluetun"
readonly LOCK_FILE="${XDG_RUNTIME_DIR:-/tmp}/hdrezka-search-deploy-${UID}.lock"

log() {
    printf '[deploy] %s\n' "$*"
}

fail() {
    log "ERROR: $*" >&2
    exit 1
}

compose() {
    local image_tag="$1"
    shift
    IMAGE_TAG="${image_tag}" docker compose \
        --project-directory "${PROJECT_DIR}" \
        -f "${COMPOSE_FILE}" \
        "$@"
}

container_health() {
    docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$1" 2>/dev/null || true
}

wait_for_healthy() {
    local container="$1"
    local timeout_seconds="$2"
    local elapsed=0
    local health=""

    while (( elapsed < timeout_seconds )); do
        health="$(container_health "${container}")"
        case "${health}" in
            healthy)
                return 0
                ;;
            unhealthy|exited|dead)
                return 1
                ;;
        esac
        sleep 2
        (( elapsed += 2 ))
    done

    return 1
}

remove_candidate() {
    local image_tag="$1"
    compose "${image_tag}" --profile candidate rm -f -s candidate >/dev/null 2>&1 || true
}

rollback() {
    local previous_tag="$1"

    log "Rolling back app to ${previous_tag}"
    compose "${previous_tag}" up -d --no-deps app
    if ! wait_for_healthy "${APP_CONTAINER}" 120; then
        docker logs --tail 100 "${APP_CONTAINER}" >&2 || true
        fail "rollback container did not become healthy"
    fi
    log "Rollback completed"
}

main() {
    local new_tag="${1:-}"
    local current_image=""
    local previous_tag=""

    [[ "${new_tag}" =~ ^[0-9a-f]{40}$ ]] || fail "expected a full 40-character Git commit SHA"
    [[ -f "${COMPOSE_FILE}" ]] || fail "missing ${COMPOSE_FILE}"
    [[ -f "${PROJECT_DIR}/.env" ]] || fail "missing ${PROJECT_DIR}/.env"

    for command in docker flock; do
        command -v "${command}" >/dev/null || fail "required command is missing: ${command}"
    done

    exec 9>"${LOCK_FILE}"
    flock -n 9 || fail "another deployment is already running"

    current_image="$(docker inspect --format '{{.Config.Image}}' "${APP_CONTAINER}" 2>/dev/null)" \
        || fail "cannot inspect ${APP_CONTAINER}"
    [[ "${current_image}" == "${IMAGE_REPOSITORY}:"* ]] \
        || fail "current app image is not rollback-safe: ${current_image}"
    previous_tag="${current_image#${IMAGE_REPOSITORY}:}"

    if [[ "${previous_tag}" == "${new_tag}" ]]; then
        log "Image ${new_tag} is already deployed"
        exit 0
    fi

    [[ "$(container_health hdrezka-postgres)" == "healthy" ]] \
        || fail "PostgreSQL is not healthy"
    [[ "$(container_health "${GLUETUN_CONTAINER}")" == "healthy" ]] \
        || fail "Gluetun is not healthy"

    log "Pulling ${IMAGE_REPOSITORY}:${new_tag}"
    docker pull "${IMAGE_REPOSITORY}:${new_tag}"

    trap "remove_candidate '${new_tag}'" EXIT
    remove_candidate "${new_tag}"

    log "Starting candidate container"
    compose "${new_tag}" --profile candidate up -d --no-deps candidate
    if ! wait_for_healthy "${CANDIDATE_CONTAINER}" 120; then
        docker logs --tail 100 "${CANDIDATE_CONTAINER}" >&2 || true
        fail "candidate did not become healthy"
    fi

    log "Checking candidate access through Gluetun"
    docker exec "${CANDIDATE_CONTAINER}" python -c \
        "import os, urllib.request; p=os.environ['REZKA_PLAYWRIGHT_PROXY']; o=urllib.request.build_opener(urllib.request.ProxyHandler({'http': p, 'https': p})); r=o.open('https://api.ipify.org', timeout=20); assert r.status == 200 and r.read().strip()"

    log "Candidate passed; deploying app"
    if ! compose "${new_tag}" up -d --no-deps app; then
        rollback "${previous_tag}"
        fail "failed to recreate app; rollback completed"
    fi

    if ! wait_for_healthy "${APP_CONTAINER}" 120; then
        docker logs --tail 100 "${APP_CONTAINER}" >&2 || true
        rollback "${previous_tag}"
        fail "new app did not become healthy; rollback completed"
    fi

    log "Deployment completed: ${previous_tag} -> ${new_tag}"
}

main "$@"
