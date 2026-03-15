#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------
# 0. Clean previous build artifacts
# ---------------------------------------------------------
echo ">>> Cleaning previous build artifacts..."
rm -rf "${SCRIPT_DIR}/rpmbuild"
rm -f "${SCRIPT_DIR}/zot"

# ---------------------------------------------------------
# 1. Download zot binary
# ---------------------------------------------------------
echo ">>> Downloading zot binary..."
ZOT_BIN="${SCRIPT_DIR}/zot"
curl -Lo "${ZOT_BIN}" \
    https://github.com/project-zot/zot/releases/latest/download/zot-linux-amd64
chmod +x "${ZOT_BIN}"

# ---------------------------------------------------------
# 2. Determine version
# ---------------------------------------------------------
echo ">>> Detecting zot version..."
ZOT_VERSION=$("${ZOT_BIN}" -v | jq -r '."distribution-spec"')
if [[ -z "${ZOT_VERSION}" || "${ZOT_VERSION}" == "null" ]]; then
    echo "ERROR: Failed to detect zot version" >&2
    exit 1
fi
echo "    Version: ${ZOT_VERSION}"

# ---------------------------------------------------------
# 3. Prepare rpmbuild tree
# ---------------------------------------------------------
RPMBUILD_DIR="${SCRIPT_DIR}/rpmbuild"
rm -rf "${RPMBUILD_DIR}"
mkdir -p "${RPMBUILD_DIR}"/{SOURCES,SPECS,BUILD,RPMS,SRPMS}

cp "${ZOT_BIN}"                       "${RPMBUILD_DIR}/SOURCES/zot"
cp "${PROJECT_DIR}/zot.service"       "${RPMBUILD_DIR}/SOURCES/zot.service"
cp "${PROJECT_DIR}/config.json"       "${RPMBUILD_DIR}/SOURCES/config.json"
cp "${PROJECT_DIR}/credentials.json"  "${RPMBUILD_DIR}/SOURCES/credentials.json"
cp "${PROJECT_DIR}/htpasswd"          "${RPMBUILD_DIR}/SOURCES/htpasswd"
cp "${PROJECT_DIR}/generate_certs.sh" "${RPMBUILD_DIR}/SOURCES/generate_certs.sh"
cp "${PROJECT_DIR}/hosts.txt"         "${RPMBUILD_DIR}/SOURCES/hosts.txt"
cp "${SCRIPT_DIR}/zot.spec"           "${RPMBUILD_DIR}/SPECS/zot.spec"

# ---------------------------------------------------------
# 4. Build RPM
# ---------------------------------------------------------
echo ">>> Building RPM (version=${ZOT_VERSION})..."
rpmbuild -bb \
    --define "_topdir ${RPMBUILD_DIR}" \
    --define "zot_version ${ZOT_VERSION}" \
    "${RPMBUILD_DIR}/SPECS/zot.spec"

# ---------------------------------------------------------
# 5. Copy result
# ---------------------------------------------------------
RPM_FILE=$(find "${RPMBUILD_DIR}/RPMS" -name "*.rpm" -type f | head -1)
if [[ -n "${RPM_FILE}" ]]; then
    cp "${RPM_FILE}" "${SCRIPT_DIR}/"
    echo ">>> RPM package built successfully:"
    echo "    $(basename "${RPM_FILE}")"
else
    echo "ERROR: RPM file not found" >&2
    exit 1
fi

# ---------------------------------------------------------
# 6. Show package file list
# ---------------------------------------------------------
echo ""
echo ">>> Package file list:"
rpm -qpl "${SCRIPT_DIR}/$(basename "${RPM_FILE}")"
