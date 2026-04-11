#!/usr/bin/env bash
# Install Anytype Heart (headless CLI) on Linux.
#
# Auto-detects architecture, downloads the latest release from GitHub,
# installs the binary to /usr/local/bin, and creates a systemd service.
#
# Usage:
#   sudo ./scripts/install-anytype.sh
#
# Environment variables:
#   ANYTYPE_VERSION  — pin a specific version tag (default: latest)
#   ANYTYPE_USER     — system user to run the service (default: openclaw)

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

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    echo "Error: this script must be run as root (sudo)." >&2
    exit 1
fi

command -v curl >/dev/null 2>&1 || { echo "Error: curl is required." >&2; exit 1; }
command -v tar >/dev/null 2>&1 || { echo "Error: tar is required." >&2; exit 1; }

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
