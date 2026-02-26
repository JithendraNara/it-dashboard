#!/bin/bash
set -euo pipefail

BASE="https://sites.pplx.app/sites/proxy/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJwcmVmaXgiOiJ3ZWIvZGlyZWN0LWZpbGVzL2NvbXB1dGVyL2I2NDBkOWJmLTQ4ZjItNDRlYS04N2U1LTAzMDYxZjg4MDVkMC9za2lsbC1ob3N0LyIsInNpZCI6ImI2NDBkOWJmLTQ4ZjItNDRlYS04N2U1LTAzMDYxZjg4MDVkMCIsImV4cCI6MTc3MjIyNDM4OH0.8rPrkz_l12W5JwvCthCdiM-7AAtFgBBBEx9y9k5E0TE/web/direct-files/computer/b640d9bf-48f2-44ea-87e5-03061f8805d0/skill-host"
DIR="$HOME/.openclaw/skills/it-dashboard-manager"

mkdir -p "${DIR}/scripts"
curl -sL "${BASE}/SKILL.md" -o "${DIR}/SKILL.md"
curl -sL "${BASE}/collect-jobs.sh" -o "${DIR}/scripts/collect-jobs.sh"
curl -sL "${BASE}/collect-trends.py" -o "${DIR}/scripts/collect-trends.py"
chmod +x "${DIR}/scripts/collect-jobs.sh" "${DIR}/scripts/collect-trends.py"
pip3 install -q requests beautifulsoup4 2>/dev/null || true
echo "Installed: $(wc -l < ${DIR}/SKILL.md) lines SKILL.md, $(wc -l < ${DIR}/scripts/collect-jobs.sh) lines collect-jobs.sh, $(wc -l < ${DIR}/scripts/collect-trends.py) lines collect-trends.py"
