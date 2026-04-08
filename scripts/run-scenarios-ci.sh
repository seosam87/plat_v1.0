#!/usr/bin/env bash
# Phase 19.1-04 — single-command CI entrypoint for the UI scenario runner.
#
# Brings up the full stack (with CI overlay), seeds the live DB via the
# idempotent scenario-runner seed module, and runs pytest inside the tester
# container. Exit code reflects pytest's exit code.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.ci.yml"

echo "==> Bringing up stack (postgres, redis, api, worker, beat)"
$COMPOSE up -d --wait postgres redis api worker beat

echo "==> Seeding live DB (idempotent)"
$COMPOSE exec -T api python -m tests.fixtures.scenario_runner.seed

echo "==> Running scenarios in tester container"
# --abort-on-container-exit so the compose run exits when tester finishes.
# --exit-code-from tester so this script's exit code reflects pytest's.
# Disable set -e around the run so we can capture the exit code.
set +e
$COMPOSE up --abort-on-container-exit --exit-code-from tester tester
TESTER_EXIT=$?
set -e

if [ "$TESTER_EXIT" -ne 0 ]; then
  echo "==> Scenario failures — artifacts at artifacts/scenarios/"
  ls -la artifacts/scenarios/ || true
fi

exit "$TESTER_EXIT"
