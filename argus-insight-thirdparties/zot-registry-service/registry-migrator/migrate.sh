#!/bin/bash
# =============================================================
# Registry Migrator
# Migrate all Docker images and Helm charts from a Zot registry
# to another OCI-compatible registry (Harbor, Zot, Docker Hub…)
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------
# Default values
# ---------------------------------------------------------
CONFIG_FILE="${SCRIPT_DIR}/config.env"
LOG_FILE="${SCRIPT_DIR}/migrate-$(date +%Y%m%d-%H%M%S).log"
DRY_RUN=false
PARALLEL_JOBS=4
RETRY_COUNT=3

# ---------------------------------------------------------
# Usage
# ---------------------------------------------------------
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Migrate all Docker images and Helm charts from a source registry
to a destination registry.

Options:
  -c, --config FILE     Configuration file (default: config.env)
  -n, --dry-run         Show what would be migrated without doing it
  -j, --jobs N          Parallel copy jobs (default: 4)
  -r, --retry N         Retry count for failed copies (default: 3)
  -l, --log FILE        Log file path
  -h, --help            Show this help

Prerequisites:
  - skopeo (https://github.com/containers/skopeo)
  - jq
  - curl
EOF
    exit 0
}

# ---------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--config) CONFIG_FILE="$2"; shift 2 ;;
        -n|--dry-run) DRY_RUN=true; shift ;;
        -j|--jobs) PARALLEL_JOBS="$2"; shift 2 ;;
        -r|--retry) RETRY_COUNT="$2"; shift 2 ;;
        -l|--log) LOG_FILE="$2"; shift 2 ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# ---------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "${msg}" | tee -a "${LOG_FILE}"
}

log_error() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*"
    echo "${msg}" | tee -a "${LOG_FILE}" >&2
}

# ---------------------------------------------------------
# Load configuration
# ---------------------------------------------------------
if [[ ! -f "${CONFIG_FILE}" ]]; then
    log_error "Configuration file not found: ${CONFIG_FILE}"
    log_error "Copy config.env.example to config.env and edit it."
    exit 1
fi

# shellcheck source=/dev/null
source "${CONFIG_FILE}"

# Validate required variables
for var in SRC_REGISTRY SRC_SCHEME DST_REGISTRY DST_SCHEME; do
    if [[ -z "${!var:-}" ]]; then
        log_error "Required variable ${var} is not set in ${CONFIG_FILE}"
        exit 1
    fi
done

# ---------------------------------------------------------
# Prerequisite check
# ---------------------------------------------------------
check_prerequisites() {
    local missing=()
    for cmd in skopeo jq curl; do
        if ! command -v "${cmd}" &>/dev/null; then
            missing+=("${cmd}")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing[*]}"
        log_error "Install them before running this script."
        exit 1
    fi
}

check_prerequisites

# ---------------------------------------------------------
# Build skopeo auth flags
# ---------------------------------------------------------
build_src_auth() {
    local args=()
    if [[ -n "${SRC_USERNAME:-}" && -n "${SRC_PASSWORD:-}" ]]; then
        args+=(--src-creds "${SRC_USERNAME}:${SRC_PASSWORD}")
    fi
    if [[ "${SRC_TLS_VERIFY:-true}" == "false" ]]; then
        args+=(--src-tls-verify=false)
    fi
    echo "${args[*]}"
}

build_dst_auth() {
    local args=()
    if [[ -n "${DST_USERNAME:-}" && -n "${DST_PASSWORD:-}" ]]; then
        args+=(--dest-creds "${DST_USERNAME}:${DST_PASSWORD}")
    fi
    if [[ "${DST_TLS_VERIFY:-true}" == "false" ]]; then
        args+=(--dest-tls-verify=false)
    fi
    echo "${args[*]}"
}

# ---------------------------------------------------------
# Zot v2 API helpers
# ---------------------------------------------------------
src_api_url() {
    echo "${SRC_SCHEME}://${SRC_REGISTRY}/v2"
}

curl_src() {
    local args=(-s -S)
    if [[ -n "${SRC_USERNAME:-}" && -n "${SRC_PASSWORD:-}" ]]; then
        args+=(-u "${SRC_USERNAME}:${SRC_PASSWORD}")
    fi
    if [[ "${SRC_TLS_VERIFY:-true}" == "false" ]]; then
        args+=(--insecure)
    fi
    curl "${args[@]}" "$@"
}

# List all repositories (handles pagination)
list_repositories() {
    local url
    url="$(src_api_url)/_catalog?n=1000"
    local repos
    repos=$(curl_src "${url}" | jq -r '.repositories[]' 2>/dev/null) || true
    echo "${repos}"
}

# List all tags for a repository
list_tags() {
    local repo="$1"
    local url
    url="$(src_api_url)/${repo}/tags/list"
    local tags
    tags=$(curl_src "${url}" | jq -r '.tags[]?' 2>/dev/null) || true
    echo "${tags}"
}

# Check if a manifest is a Helm chart (OCI artifact)
is_helm_chart() {
    local repo="$1"
    local tag="$2"
    local url
    url="$(src_api_url)/${repo}/manifests/${tag}"
    local media_type
    media_type=$(curl_src -H "Accept: application/vnd.oci.image.manifest.v1+json" \
        "${url}" | jq -r '.config.mediaType // empty' 2>/dev/null) || true

    if [[ "${media_type}" == "application/vnd.cncf.helm.config.v1+json" ]]; then
        return 0
    fi
    return 1
}

# ---------------------------------------------------------
# Copy a single image/artifact
# ---------------------------------------------------------
copy_image() {
    local repo="$1"
    local tag="$2"
    local src_ref="${SRC_SCHEME}://${SRC_REGISTRY}/${repo}:${tag}"

    # Determine destination repo (apply prefix if configured)
    local dst_repo="${repo}"
    if [[ -n "${DST_PROJECT_PREFIX:-}" ]]; then
        dst_repo="${DST_PROJECT_PREFIX}/${repo}"
    fi
    local dst_ref="${DST_SCHEME}://${DST_REGISTRY}/${dst_repo}:${tag}"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log "[DRY-RUN] ${repo}:${tag} -> ${dst_repo}:${tag}"
        return 0
    fi

    local src_auth dst_auth
    src_auth=$(build_src_auth)
    dst_auth=$(build_dst_auth)

    local attempt=0
    while (( attempt < RETRY_COUNT )); do
        attempt=$((attempt + 1))
        # shellcheck disable=SC2086
        if skopeo copy --all \
            ${src_auth} \
            ${dst_auth} \
            "docker://${SRC_REGISTRY}/${repo}:${tag}" \
            "docker://${DST_REGISTRY}/${dst_repo}:${tag}" 2>>"${LOG_FILE}"; then
            log "[OK] ${repo}:${tag} -> ${dst_repo}:${tag}"
            return 0
        fi
        log_error "Attempt ${attempt}/${RETRY_COUNT} failed for ${repo}:${tag}"
        sleep $((attempt * 2))
    done

    log_error "FAILED after ${RETRY_COUNT} attempts: ${repo}:${tag}"
    return 1
}

# ---------------------------------------------------------
# Main migration
# ---------------------------------------------------------
main() {
    log "=========================================="
    log "Registry Migrator"
    log "=========================================="
    log "Source:      ${SRC_REGISTRY}"
    log "Destination: ${DST_REGISTRY}"
    log "Dry-run:     ${DRY_RUN}"
    log "Parallel:    ${PARALLEL_JOBS}"
    log "Log file:    ${LOG_FILE}"
    log "=========================================="

    # Enumerate all repositories
    log ">>> Listing all repositories..."
    local repos
    repos=$(list_repositories)

    if [[ -z "${repos}" ]]; then
        log "No repositories found in source registry."
        exit 0
    fi

    local repo_count=0
    local image_count=0
    local helm_count=0
    local fail_count=0

    # Build a work queue: repo:tag pairs
    local work_queue=()

    while IFS= read -r repo; do
        [[ -z "${repo}" ]] && continue
        repo_count=$((repo_count + 1))

        local tags
        tags=$(list_tags "${repo}")
        if [[ -z "${tags}" ]]; then
            log "  [SKIP] ${repo} (no tags)"
            continue
        fi

        while IFS= read -r tag; do
            [[ -z "${tag}" ]] && continue
            work_queue+=("${repo}|${tag}")
        done <<< "${tags}"
    done <<< "${repos}"

    local total=${#work_queue[@]}
    log ">>> Found ${repo_count} repositories, ${total} total image/tag combinations"
    log ""

    # Process the work queue
    local current=0
    local pids=()

    for item in "${work_queue[@]}"; do
        local repo="${item%%|*}"
        local tag="${item##*|}"
        current=$((current + 1))

        # Classify artifact type for reporting
        local artifact_type="image"
        if is_helm_chart "${repo}" "${tag}" 2>/dev/null; then
            artifact_type="helm-chart"
            helm_count=$((helm_count + 1))
        else
            image_count=$((image_count + 1))
        fi

        log "[${current}/${total}] (${artifact_type}) ${repo}:${tag}"

        if (( PARALLEL_JOBS <= 1 )); then
            copy_image "${repo}" "${tag}" || fail_count=$((fail_count + 1))
        else
            copy_image "${repo}" "${tag}" &
            pids+=($!)

            # Throttle parallel jobs
            if (( ${#pids[@]} >= PARALLEL_JOBS )); then
                for pid in "${pids[@]}"; do
                    wait "${pid}" || fail_count=$((fail_count + 1))
                done
                pids=()
            fi
        fi
    done

    # Wait for remaining background jobs
    for pid in "${pids[@]}"; do
        wait "${pid}" || fail_count=$((fail_count + 1))
    done

    # Summary
    log ""
    log "=========================================="
    log "Migration completed"
    log "  Repositories: ${repo_count}"
    log "  Docker images: ${image_count}"
    log "  Helm charts:   ${helm_count}"
    log "  Failed:        ${fail_count}"
    log "=========================================="

    if (( fail_count > 0 )); then
        log_error "Some artifacts failed to migrate. Check the log: ${LOG_FILE}"
        exit 1
    fi
}

main
