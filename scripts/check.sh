#!/usr/bin/env bash
# scripts/check.sh — Run all quality gates locally, mirroring the CI pipeline.
#
# Usage:
#   ./scripts/check.sh           # check-only (no changes)
#   ./scripts/check.sh --fix     # auto-fix safe Ruff issues, then check
#   ./scripts/check.sh --fast    # skip pip-audit (useful on slow/offline machines)
#
# Exit code: 0 if all gates pass, 1 if any gate fails.
# Each gate is run independently so all failures are visible in one pass.
#
# Gate order mirrors .github/workflows/ci.yml:
#   1. Lint & Format   (ruff check, stale noqa, ruff format)
#   2. Type Check      (mypy)
#   3. Tests           (pytest + coverage)
#   4. Security        (pip-audit)

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
FIX=false
FAST=false
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0
FAILED_GATES=()

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
for arg in "$@"; do
    case "$arg" in
        --fix)  FIX=true ;;
        --fast) FAST=true ;;
        --help|-h)
            echo "Usage: ./scripts/check.sh [--fix] [--fast]"
            echo ""
            echo "  --fix   Auto-fix safe Ruff violations before checking"
            echo "  --fast  Skip pip-audit (useful offline or on slow CI runners)"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg  (use --help for usage)" >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
BOLD="\033[1m"
GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
CYAN="\033[1;36m"
RESET="\033[0m"

header() { echo -e "\n${CYAN}━━━  $1  ━━━${RESET}"; }
pass()   { echo -e "${GREEN}  ✓  $1${RESET}"; PASS=$((PASS + 1)); }
fail()   { echo -e "${RED}  ✗  $1${RESET}"; FAIL=$((FAIL + 1)); FAILED_GATES+=("$1"); }
skip()   { echo -e "${YELLOW}  ⊘  $1 (skipped)${RESET}"; }
run()    { echo -e "  ${BOLD}$*${RESET}"; }

gate() {
    # gate <label> <command...>
    local label="$1"; shift
    header "$label"
    run "$@"
    if "$@"; then
        pass "$label"
    else
        fail "$label"
    fi
}

# ---------------------------------------------------------------------------
# Activate virtualenv if present
# ---------------------------------------------------------------------------
VENV="$PROJECT_ROOT/.venv"
if [[ -f "$VENV/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
fi

cd "$PROJECT_ROOT"

echo -e "\n${BOLD}Quality gates — $(date '+%Y-%m-%d %H:%M:%S')${RESET}"
echo -e "Project root: ${PROJECT_ROOT}"
[[ "$FIX" == "true" ]] && echo -e "${YELLOW}  Auto-fix mode enabled (--fix)${RESET}"

# ---------------------------------------------------------------------------
# ── JOB 1: Lint & Format ────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

if [[ "$FIX" == "true" ]]; then
    header "Ruff lint — auto-fix (safe)"
    run uv run ruff check --fix .
    uv run ruff check --fix . || true
fi

gate "Ruff lint" \
    uv run ruff check .

gate "Ruff lint — stale noqa (RUF100)" \
    uv run ruff check --extend-select RUF100 .

if [[ "$FIX" == "true" ]]; then
    header "Ruff format — apply"
    run uv run ruff format .
    uv run ruff format . || true
fi

gate "Ruff format" \
    uv run ruff format --check .

# ---------------------------------------------------------------------------
# ── JOB 2: Type Check ───────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

gate "Mypy" \
    uv run mypy .

# ---------------------------------------------------------------------------
# ── JOB 3: Tests + Coverage ─────────────────────────────────────────────────
# ---------------------------------------------------------------------------

gate "Pytest + coverage" \
    uv run pytest --cov=. --cov-report=term-missing --cov-fail-under=90

# ---------------------------------------------------------------------------
# ── JOB 4: Security ─────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

if [[ "$FAST" == "true" ]]; then
    skip "pip-audit (--fast)"
else
    # TODO(cmobley, 2026-Q2): Remove ignores when snaptrade-python-sdk
    # upgrades its cryptography dependency past 46.0.6.
    gate "pip-audit" \
        uv run pip-audit \
            --ignore-vuln CVE-2024-12797 \
            --ignore-vuln CVE-2026-26007 \
            --ignore-vuln CVE-2026-34073
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}━━━  Summary  ━━━${RESET}"
echo -e "  Passed : ${GREEN}${PASS}${RESET}"
echo -e "  Failed : ${RED}${FAIL}${RESET}"

if [[ "${#FAILED_GATES[@]}" -gt 0 ]]; then
    echo -e "\n${RED}${BOLD}  Failed gates:${RESET}"
    for g in "${FAILED_GATES[@]}"; do
        echo -e "${RED}    • ${g}${RESET}"
    done
    echo ""
    exit 1
else
    echo -e "\n${GREEN}${BOLD}  All gates passed.${RESET}\n"
    exit 0
fi
