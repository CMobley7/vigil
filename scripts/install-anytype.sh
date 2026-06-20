#!/usr/bin/env bash
# Install Anytype Heart (headless CLI) on Linux.
#
# Auto-detects architecture, downloads a pinned release from GitHub, installs
# the binary to /usr/local/bin, and creates a systemd service.
#
# Usage:
#   sudo ./scripts/install-anytype.sh
#
# Environment variables:
#   ANYTYPE_VERSION        — required version tag to install (e.g., v0.35.0)
#   ANYTYPE_SHA256         — expected SHA-256 of the downloaded tarball
#   ANYTYPE_ALLOW_LATEST   — set to true to resolve the latest release
#   ANYTYPE_SKIP_CHECKSUM  — set to true only for exploratory installs
#   ANYTYPE_USER           — system user to run the service (default: openclaw)

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
INSTALL_DIR="/usr/local/bin"
SERVICE_NAME="anytype"
ANYTYPE_USER="${ANYTYPE_USER:-openclaw}"
ANYTYPE_DATA_DIR="/var/lib/anytype"
GITHUB_REPO="anyproto/anytype-heart"
VERSION="${ANYTYPE_VERSION:-}"
ALLOW_LATEST="${ANYTYPE_ALLOW_LATEST:-false}"
EXPECTED_SHA256="${ANYTYPE_SHA256:-}"
SKIP_CHECKSUM="${ANYTYPE_SKIP_CHECKSUM:-false}"

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    echo "Error: this script must be run as root (sudo)." >&2
    exit 1
fi

command -v curl >/dev/null 2>&1 || { echo "Error: curl is required." >&2; exit 1; }
command -v tar >/dev/null 2>&1 || { echo "Error: tar is required." >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "Error: sha256sum is required." >&2; exit 1; }

# ---------------------------------------------------------------------------
# Detect architecture
# ---------------------------------------------------------------------------
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)  ARCH_SUFFIX="amd64" ;;
    aarch64) ARCH_SUFFIX="arm64" ;;
    *)
        echo "Error: unsupported architecture: $ARCH" >&2
        exit 1
        ;;
esac

echo "→ Detected architecture: ${ARCH} (${ARCH_SUFFIX})"

# ---------------------------------------------------------------------------
# Resolve version
# ---------------------------------------------------------------------------
if [[ -z "$VERSION" && "$ALLOW_LATEST" != "true" ]]; then
    echo "Error: ANYTYPE_VERSION is required for reproducible installs." >&2
    echo "Set ANYTYPE_ALLOW_LATEST=true only for exploratory installs." >&2
    exit 1
fi

if [[ -z "$VERSION" ]]; then
    echo "→ Fetching latest release tag from GitHub..."
    VERSION="$(curl -fsSL "https://api.github.com/repos/${GITHUB_REPO}/releases/latest" \
        | grep '"tag_name"' \
        | head -1 \
        | sed -E 's/.*"tag_name":\s*"([^"]+)".*/\1/')"
fi

if [[ -z "$VERSION" ]]; then
    echo "Error: could not determine latest version." >&2
    exit 1
fi

echo "→ Installing Anytype Heart ${VERSION} for ${ARCH_SUFFIX}"

# ---------------------------------------------------------------------------
# Download and install binary
# ---------------------------------------------------------------------------
TARBALL="anytype-heart-${VERSION}-linux-${ARCH_SUFFIX}.tar.gz"
DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download/${VERSION}/${TARBALL}"
TMP_DIR="$(mktemp -d)"

echo "→ Downloading ${DOWNLOAD_URL}..."
if ! curl -fSL -o "${TMP_DIR}/${TARBALL}" "$DOWNLOAD_URL"; then
    # Fallback: try without version prefix in the filename
    TARBALL="anytype-heart-linux-${ARCH_SUFFIX}.tar.gz"
    DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download/${VERSION}/${TARBALL}"
    echo "→ Retrying with fallback URL: ${DOWNLOAD_URL}..."
    curl -fSL -o "${TMP_DIR}/${TARBALL}" "$DOWNLOAD_URL"
fi

if [[ -n "$EXPECTED_SHA256" ]]; then
    echo "→ Verifying SHA-256..."
    printf '%s  %s\n' "$EXPECTED_SHA256" "${TMP_DIR}/${TARBALL}" | sha256sum -c -
elif [[ "$SKIP_CHECKSUM" == "true" ]]; then
    echo "⚠ ANYTYPE_SKIP_CHECKSUM=true; downloaded tarball was not verified." >&2
else
    echo "Error: ANYTYPE_SHA256 is required to verify the downloaded tarball." >&2
    echo "Set ANYTYPE_SKIP_CHECKSUM=true only for exploratory installs." >&2
    rm -rf "${TMP_DIR}"
    exit 1
fi

echo "→ Extracting..."
tar xf "${TMP_DIR}/${TARBALL}" -C "${TMP_DIR}"

# Find the binary (may be nested in a directory)
BINARY="$(find "${TMP_DIR}" -name 'anytype-heart' -o -name 'anytype' | head -1)"
if [[ -z "$BINARY" ]]; then
    echo "Error: could not find anytype binary in archive." >&2
    rm -rf "${TMP_DIR}"
    exit 1
fi

install -m 755 "$BINARY" "${INSTALL_DIR}/anytype"
rm -rf "${TMP_DIR}"

echo "→ Installed to ${INSTALL_DIR}/anytype"
"${INSTALL_DIR}/anytype" --version 2>/dev/null || true

# ---------------------------------------------------------------------------
# Create system user (if it doesn't exist)
# ---------------------------------------------------------------------------
if ! id "$ANYTYPE_USER" &>/dev/null; then
    echo "→ Creating system user: ${ANYTYPE_USER}"
    useradd --system --shell /usr/sbin/nologin --home-dir "$ANYTYPE_DATA_DIR" "$ANYTYPE_USER"
fi

mkdir -p "$ANYTYPE_DATA_DIR"
chown "$ANYTYPE_USER:$ANYTYPE_USER" "$ANYTYPE_DATA_DIR"

# ---------------------------------------------------------------------------
# Create systemd service
# ---------------------------------------------------------------------------
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Anytype Heart — headless local-first knowledge base
After=network.target

[Service]
Type=simple
User=${ANYTYPE_USER}
WorkingDirectory=${ANYTYPE_DATA_DIR}
ExecStart=${INSTALL_DIR}/anytype serve
Restart=on-failure
RestartSec=5
LimitNOFILE=65536

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${ANYTYPE_DATA_DIR}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "✓ Anytype Heart ${VERSION} installed successfully."
echo ""
echo "Next steps:"
echo "  1. Start the service:    sudo systemctl start anytype"
echo "  2. Create an API key:    anytype auth apikey create --name vigil"
echo "  3. List spaces:          curl -H 'Authorization: Bearer <key>' http://127.0.0.1:31012/v1/spaces"
echo ""
