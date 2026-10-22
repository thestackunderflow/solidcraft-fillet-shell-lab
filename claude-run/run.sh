#!/usr/bin/env bash
# One logged, headless Claude Code run against SolidCraft 0.17.0 (clean: no user CLAUDE.md, no user settings, no memory).
#   bash claude-run/run.sh plain|named RUN_ID
# plain: an open-top box, 80 x 60 x 30, 2 mm walls and floor, vertical corners rounded to 10 mm; no order given.
# named: the same + "Round the corners before you hollow it out."
# Claude Code --stdio--> docker run -i ... [mcp_log_proxy.py --watchdog 180 --stdio--> solidcraft-cli mcp]; only the
# solidcraft tools. From solidcraft-resize-lab/claude-run/run.sh, plus (PLAN v2 5.2):
#   1. a budget gate: no start when the logged total + $1.50 would pass $10.00 (out/runs/BUDGET.log);
#   2. cost survives a kill: an empty claude-output.json is logged at the full $1.50 cap ("killed-floor");
#   3. the proxy's watchdog writes HANG after 180 s without a reply and kills the server; this script then kills claude.
set -euo pipefail
ARM=$1; RUN=$2
cd "$(dirname "$0")/.."
LAB="$(pwd -W 2>/dev/null || pwd)"
OUT=out/runs/$ARM-$RUN
LOGB=out/runs/BUDGET.log
MODEL="${MODEL:-claude-sonnet-5-5}"
BUDGET="${BUDGET:-1.50}"
CAP_TOTAL=10.00
mkdir -p out/runs
TOTAL=$(awk -F'\t' '!/^#/ && NF>=2 {s+=$2} END {printf "%.4f", s+0}' "$LOGB" 2>/dev/null || echo 0)
if awk -v t="$TOTAL" -v b="$BUDGET" -v c="$CAP_TOTAL" 'BEGIN {exit !(t + b > c)}'; then
  echo "BUDGET STOP: logged total \$$TOTAL + \$$BUDGET would pass \$$CAP_TOTAL"; exit 2
fi
[ -e "$OUT/run-meta.json" ] && { echo "refusing to overwrite $OUT"; exit 3; }
mkdir -p "$OUT"
NAME="fsl-$ARM-$RUN-$$"

cat > "$OUT/mcp-config.json" <<JSON
{"mcpServers": {"solidcraft": {"command": "docker", "args": ["run", "-i", "--rm", "--name", "$NAME", "-v", "$LAB/proxy:/proxy:ro", "-v", "$LAB/$OUT:/lab/out", "solidcraft-fillet-shell-lab:0.17.0", "python3", "/proxy/mcp_log_proxy.py", "--log", "/lab/out/transcript.jsonl", "--png-dir", "/lab/out", "--watchdog", "180", "--", "solidcraft-cli", "mcp", "--allow-path", "/lab/out"]}}}
JSON

BOX="Use the solidcraft MCP tools to make a 3D-printable open-top box in millimetres: 80 wide along X, 60 deep along Y, 30 tall along Z, with walls and floor 2 mm thick and the four vertical outside corners rounded to a 10 mm radius. Export it as STL to /lab/out/box.stl. Report the bounding box, the volume and any step that failed."
if [ "$ARM" = plain ]; then PROMPT="$BOX"; else PROMPT="$BOX Round the corners before you hollow it out."; fi
printf '%s\n' "$PROMPT" > "$OUT/prompt.txt"

T0=$(date +%s)
set +e
MSYS_NO_PATHCONV=1 timeout 900 "${CLAUDE:-claude}" -p "$PROMPT" --model "$MODEL" \
  --mcp-config "$OUT/mcp-config.json" --strict-mcp-config \
  --tools "" --allowedTools "mcp__solidcraft__*" --permission-mode dontAsk \
  --max-budget-usd "$BUDGET" --no-session-persistence \
  --setting-sources project,local --settings '{"claudeMdExcludes":["**/.claude/CLAUDE.md"],"autoMemoryEnabled":false}' \
  --output-format json < /dev/null > "$OUT/claude-output.json" &
PID=$!
HUNG=0
while kill -0 "$PID" 2>/dev/null; do
  if grep -q '"HANG"' "$OUT/transcript.jsonl" 2>/dev/null; then
    HUNG=1
    WP=$(cat /proc/$PID/winpid 2>/dev/null || true)
    kill "$PID" 2>/dev/null; [ -n "$WP" ] && taskkill //F //T //PID "$WP" >/dev/null 2>&1
    docker kill "$NAME" >/dev/null 2>&1
    break
  fi
  sleep 3
done
wait "$PID"; RC=$?
set -e
docker kill "$NAME" >/dev/null 2>&1 || true
# no host path in the saved config (the lab may be published)
sed -i "s#$LAB#\$LAB#g" "$OUT/mcp-config.json"
COST=$(python -c "import json,sys
try: print(json.load(open(sys.argv[1]))['total_cost_usd'])
except Exception: print('')" "$OUT/claude-output.json")
if [ -z "$COST" ]; then COST=$BUDGET; KIND=killed-floor; else KIND=logged; fi
NEW=$(awk -v t="$TOTAL" -v c="$COST" 'BEGIN {printf "%.4f", t + c}')
printf '%s\t%s\t%s\t%s\n' "$ARM-$RUN" "$COST" "$KIND" "$NEW" >> "$LOGB"
echo "{\"arm\": \"$ARM\", \"run\": \"$RUN\", \"model\": \"$MODEL\", \"budget_usd\": $BUDGET, \"exit\": $RC, \"hang_killed\": $HUNG, \"wall_s\": $(( $(date +%s) - T0 )), \"claude_version\": \"$(${CLAUDE:-claude} --version | head -1)\", \"solidcraft\": \"0.17.0\"}" > "$OUT/run-meta.json"
cat "$OUT/run-meta.json"; echo "cost $COST ($KIND), running total \$$NEW"
