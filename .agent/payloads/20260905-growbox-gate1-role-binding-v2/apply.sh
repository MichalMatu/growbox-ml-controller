#!/usr/bin/env bash
set -euo pipefail

# Retry the immutable Gate 1 edit payload after a verification-only memory-limit failure.
# The v1 edit and focused tests passed; no source change is introduced by this wrapper.
git fetch -q origin agent-control
BASE_PAYLOAD=/tmp/growbox-gate1-role-binding-v1-retry.sh
git show origin/agent-control:.agent/payloads/20260905-growbox-gate1-role-binding-v1/apply.sh > "$BASE_PAYLOAD"
bash "$BASE_PAYLOAD"
