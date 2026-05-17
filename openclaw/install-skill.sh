#!/usr/bin/env bash
set -euo pipefail

INSTALL_REF="${IT_DASHBOARD_INSTALL_REF:-main}"
RAW_BASE="https://raw.githubusercontent.com/JithendraNara/it-dashboard/${INSTALL_REF}/openclaw"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="${HOME}/.openclaw/skills/it-dashboard-manager"

FILES=(
  "SKILL.md:53d1d9fb264b8b063e5324f216860aad651ad0c2ddc9edf8fda6ec129d73b3da"
  "scripts/collect-jobs.sh:3e416f5af5410b34710c4c3fe520e60b3766e520a40143c24fa68f3ae14c55fd"
  "scripts/collect-trends.py:e27d5a4b937375e061cf3a329909513ebb8098a9e70e1dff9d4b81d675f9c5f0"
  "scripts/collect-jobs-agent-browser.sh:ebbc0ed4f3292b3a253866cbb5a7afc21c18d77c19a54a42163447635f21f50f"
  "scripts/push-jobs-snapshot.py:5d5f496bcb46f053385f99f90de861a84764d5a800961c264b8e5369f8580875"
)

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

install_file() {
  local rel_path="$1"
  local expected_hash="$2"
  local src="${SCRIPT_DIR}/${rel_path}"
  local dest="${DIR}/${rel_path}"
  local tmp

  mkdir -p "$(dirname "$dest")"
  tmp="$(mktemp)"

  if [ -f "$src" ]; then
    cp "$src" "$tmp"
  else
    curl -fsSL "${RAW_BASE}/${rel_path}" -o "$tmp"
  fi

  local actual_hash
  actual_hash="$(sha256_file "$tmp")"
  if [ "$actual_hash" != "$expected_hash" ]; then
    rm -f "$tmp"
    echo "ERROR: checksum mismatch for ${rel_path}" >&2
    echo "expected: ${expected_hash}" >&2
    echo "actual:   ${actual_hash}" >&2
    exit 1
  fi

  mv "$tmp" "$dest"
}

mkdir -p "${DIR}/scripts"

for entry in "${FILES[@]}"; do
  install_file "${entry%%:*}" "${entry##*:}"
done

chmod +x \
  "${DIR}/scripts/collect-jobs.sh" \
  "${DIR}/scripts/collect-trends.py" \
  "${DIR}/scripts/collect-jobs-agent-browser.sh" \
  "${DIR}/scripts/push-jobs-snapshot.py"

pip3 install -q requests beautifulsoup4 2>/dev/null || true

echo "Installed verified IT dashboard OpenClaw skill to ${DIR}"
