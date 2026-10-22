#!/usr/bin/env bash
# The six paid runs, alternating; stops on a budget gate or after two infra failures.
cd "$(dirname "$0")/.."
INFRA=0
for n in 1 2 3; do for arm in plain named; do
  echo "=== $arm-$n $(date)"
  bash claude-run/run.sh $arm $n; rc=$?
  [ $rc -eq 2 ] && { echo "budget stop"; exit 0; }
  if grep -q '"hang_killed": 1' out/runs/$arm-$n/run-meta.json 2>/dev/null || grep -q killed-floor <(tail -1 out/runs/BUDGET.log); then
    INFRA=$((INFRA+1)); echo "infra failure $INFRA"
    [ $INFRA -ge 2 ] && { echo "two infra failures: stop"; exit 0; }
  fi
done; done
