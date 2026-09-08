#!/usr/bin/env bash
set -euo pipefail

git show FETCH_HEAD:.agent/scripts/20260908-a5-1-schedule-intent-v1.py > /tmp/a5_1_edit.py
git show FETCH_HEAD:.agent/scripts/20260908-a5-1-schedule-intent-v1-run.sh > /tmp/a5_1_run.sh
bash /tmp/a5_1_run.sh
