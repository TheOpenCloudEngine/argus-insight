#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/versions.env"

MAVEN_REPO_URL="${MAVEN_REPO_URL:-http://10.0.1.50:8081/repository/maven-public/}"
DIST_DIR="${SCRIPT_DIR}/dist"
BUILD_DIR="${DIST_DIR}/build"
SOURCE_DIR="${DIST_DIR}/source"
SOURCE_TARBALL="${DIST_DIR}/unitycatalog-${UNITY_CATALOG_VERSION}.tar.gz"

echo "=== Unity Catalog ${UNITY_CATALOG_VERSION} Build ==="
echo "Maven Repo: ${MAVEN_REPO_URL}"

# 1. Download source
if [ ! -f "${SOURCE_TARBALL}" ]; then
    mkdir -p "${DIST_DIR}"
    echo "[1/4] Downloading Unity Catalog ${UNITY_CATALOG_VERSION} source..."
    curl -sSL -o "${SOURCE_TARBALL}" \
        "https://github.com/unitycatalog/unitycatalog/archive/refs/tags/v${UNITY_CATALOG_VERSION}.tar.gz"
else
    echo "[1/4] Source tarball already exists, skipping download."
fi

# 2. Extract source
echo "[2/4] Extracting source..."
rm -rf "${SOURCE_DIR}"
mkdir -p "${SOURCE_DIR}"
tar -xzf "${SOURCE_TARBALL}" -C "${SOURCE_DIR}" --strip-components=1

# 3. Configure sbt repositories
echo "[3/4] Configuring sbt Maven repository..."
mkdir -p ~/.sbt
printf '[repositories]\n  local\n  maven-central\n  argus-maven: %s, allowInsecureProtocol\n' \
    "${MAVEN_REPO_URL}" > ~/.sbt/repositories

# 4. Build
echo "[4/4] Building Unity Catalog (this may take several minutes)..."
cd "${SOURCE_DIR}"
build/sbt -batch -Dsbt.override.build.repos=false createTarball

# Extract built artifacts
echo "Extracting build artifacts..."
mkdir -p "${BUILD_DIR}"
tar -xzf target/unitycatalog-*.tar.gz -C "${BUILD_DIR}" --strip-components=1

echo ""
echo "=== Build complete ==="
echo "Artifacts: ${BUILD_DIR}/"
ls -la "${BUILD_DIR}/"
