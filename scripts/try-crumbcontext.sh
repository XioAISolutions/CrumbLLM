#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIR="$ROOT_DIR/incubator/crumbcontext"
VENV_DIR="${CRUMBCONTEXT_VENV:-$ROOT_DIR/.venv-crumbcontext}"
OUT_DIR="${1:-$ROOT_DIR/crumbcontext-proof}"

printf '\n🧠 CrumbContext quick launch\n'
printf '   exact facts stay exact; stale context takes the cheaper lane\n\n'

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e "$PACKAGE_DIR"

crumbcontext benchmark --out "$OUT_DIR"

printf '\n✅ Proof bundle created\n'
printf '   report:     %s/report.html\n' "$OUT_DIR"
printf '   share card: %s/share-card.svg\n' "$OUT_DIR"
printf '   raw result: %s/benchmark.json\n\n' "$OUT_DIR"

case "$(uname -s)" in
  Darwin) open "$OUT_DIR/report.html" >/dev/null 2>&1 || true ;;
  Linux) command -v xdg-open >/dev/null && xdg-open "$OUT_DIR/report.html" >/dev/null 2>&1 || true ;;
esac
