# SolidCraft: a hollow box with rounded corners, and why the order matters (a test-first lab)

**Lab snapshot: 21 Oct 2026.** SolidCraft **0.17.0** (release tarball, SHA256SUMS checked), driven over MCP. Claude Code
2.1.303 for the agent runs. Everything runs in Docker; nothing is installed on the host.

## The part

An open-top box, 80 × 60 × 30 mm, walls and floor 2 mm, the four vertical outside corners rounded. Two orders:
**FS** = round the corners (`solid.fillet`), then hollow it (`solid.shell`); **SF** = hollow it, then round.

## What the lab shows (no AI)

| Order, radius | SolidCraft 0.17.0 says | Corner wall (STL fit / SolidCraft) |
|---|---|---|
| FS, 10 mm | `ok: true` | 2.0000 / 2.0000 mm |
| SF, 10 mm | refused: "… the largest radius that fits is 6.82 mm" | — |
| SF, 6 mm | `ok: true`, no warning | **0.3431 / 0.3431 mm** |
| SF, 6.82 mm (the offered radius) | `ok: true`, no warning | **0.0035 / 0.0035 mm** |

Every wall matches hand geometry (R − (R − 2)·√2), every volume is within 0.003% of its formula, 3 of 3 repeats are
identical. 0.18.1 gives the same results. 0.16.2 is different: it refused SF at 6 mm and offered 4 mm (a 1.17 mm wall),
the change made by SolidCraft PR #2852 in 0.17.0.

The two step files in `steps/` are SolidCraft scripts (`{"commands": [...]}`): `solidcraft-cli run
steps/fillet-then-shell.json --out box.stl` builds the box; `steps/shell-then-fillet.json` stops at step 6 with the
refusal and writes nothing.

## Agent runs (`claude-run/`)

`run.sh plain|named N`: one clean headless Claude Code run (no user CLAUDE.md, settings or memory; only SolidCraft's MCP
tools; every JSON-RPC line logged by `proxy/mcp_log_proxy.py`, which also ends a call with no reply after 180 s). Six runs,
alternating, `claude-sonnet-5-5`, `--max-budget-usd 1.50` each: **all six rounded first and all six parts are in spec;
total $0.24** (`out/runs/SCORES.json`, `out/runs/BUDGET.log`). The plain prompt never says the order.

## Run it

```bash
docker build -t solidcraft-fillet-shell-lab:0.17.0 .
docker compose run --rm unit-tests          # measurer, step files, client timeout (+ tests/test_proxy_watchdog.py, tests/test_score.py)
docker compose run --rm solidcraft-tests    # probe cells live vs the record, step files, set_parameter
docker compose run --rm evidence
docker run --rm -v "$PWD:/work" -v "$PWD/out/probe/0.17.0:/lab/out" -w /work solidcraft-fillet-shell-lab:0.17.0 python3 probe/probe.py 0.17.0 all 3
docker run --rm -v "$PWD:/work" -w /work solidcraft-fillet-shell-lab:0.17.0 python3 video/make_frames.py
bash claude-run/run.sh plain 1              # paid: Claude Code on the host
docker compose run --rm score
```

Red then green: `out/red-phase-*.log`, `out/green-phase-*.log`. `mcp-config.json` files show the host folder as `$LAB`.

## Licence

Lab code: Apache License 2.0 (`LICENSE`). SolidCraft is "MIT OR Apache-2.0"; the Docker image downloads its official
release and does not redistribute it.
