# LAB-STATUS (21 Oct 2026)

**State: lab done, render-ready inputs written. Next: the script (plan `PLAN.md` v2 §6) and its 3 reviewers.**
Plan folder: `Refream-Canvas/inputs/video-plans/2026-10-20-solidcraft-fillet-shell/` (`PLAN.md` v2, `DECISIONS.md`,
`PROBE-RESULT.md`, `ACCURACY.md`). Card sources pinned at **f384450** (`video/panel-sources.json`).

## Verdict and numbers

- Probe: **GO-A + GO-B** on SolidCraft 0.17.0 (pinned; 0.18.1 identical; 0.16.2 differs per PR #2852). $0.
- SF-10 refused: "… the largest radius that fits is 6.82 mm". FS-10 builds: volume 23 795.10 vs 23 795.04 (+0.0002%),
  wall 2.0000. SF-6 builds with no warning: wall 0.3431 (two methods). SF at the offered 6.82: builds, wall **0.0035 mm**.
- Agent runs: 6 (plain 3, named 3), **$0.2377 total** (cap $10; each ≤ $0.06), 0 HANG, 0 refusals, **6 of 6 rounded
  first**, 6 of 6 parts in spec.
- P4: 4 bosses + a lip on the rounded rim build on 0.17.0; the lid itself is untested.

## Tests (red → green, logs in `out/`)

| Suite | Red | Green |
|---|---|---|
| Probe PT1-PT4 (measurer, step-file format, client timeout) | 36 failed, 1 error | 39 passed |
| SolidCraft cells, step files, `solidcraft-cli run`, set_parameter | 1 failed, 13 errors | 16 passed |
| Proxy watchdog | 2 failed | 2 passed |
| Scorer | 5 failed | 5 passed |
| Off-centre measurer fix (found when the agent boxes sat at 0..80) | 2 failed | passed |
| Evidence (numbers, phone widths, JSON views, pins, no host paths) | 2 failed | 13 passed |
| **Whole suite** | | **77 passed** (`out/green-phase-all.log`) |

Note: running `solidcraft-tests` rewrites `out/steps/*.jsonl` and `out/set_parameter/transcript.jsonl` (new timestamps),
so the pinned files then differ: `git checkout -- out/steps out/set_parameter` after a re-run, or re-pin with
`python video/pin_sources.py` after a new commit.

## Render-ready outputs (`video/`)

| File | For |
|---|---|
| `frames/frame0-both-boxes.png` (1920×1080) | Frame 0 / thumbnail: ONE SolidCraft render, both boxes, same camera. Left: shell only, the 4 edges the refused fillet named as thin red rods (our highlight bodies: disclose "edges highlighted"). Right: round first, R10. Tags ✗ REFUSED / ✓ BUILT are added by the engine. `frame0-both-boxes-plain.png` without the rods |
| `frames/section-*.png`, `section-*-corner.png` | z = 15 sections (SolidCraft `snapshot --section z=15`): shell-only, FS-10, FS-6, SF-6, SF-6.82; corner close-ups for phones |
| `frames/iso-*.png` | single-box iso renders |
| `frames/*.script.json` | the exact script each image was rendered from |
| `terminal-refusal-clause.txt` | the one clause the toolcall cannot hold (39 cols) |
| `terminal-proof.txt` | wall by two methods (R10 FS, R6 SF, R6.82 SF) + volume vs hand count (7 rows, ≤ 44 cols) |
| `terminal-runs.txt`, `terminal-prompts.txt` | chapter 7 |
| `rule-card.txt` | `SolidCraft 0.17` / `1. Round first, then shell` / `2. Its offered radius can be too thin` / `3. Measure the wall` |
| `toolcalls.json` | Toolcall 1 (refused, `rolled_back`, `undone`, `failed.index` 5), 3 (built, `completed: 6`), 4 (`measure`), GO-B SF-6 and SF-6.82 (`ok: true · warning: null`); args ≤ 160, result ≤ 60 |
| `json-cards.json` | JSON 2 (`set_parameter` wall, focusKey value = 2, "value, two"), JSON 1a (the shell step, mark `solid.shell`), JSON 1b (the fillet step's params, focusKey radius = 10, "radius, ten"); all `cols` 44, no-AI sources |
| JSON A/B | `steps/shell-then-fillet.json` vs `steps/fillet-then-shell.json` (12 rows, ≤ 64 cols; rows 7-11 differ) |
| `panel-sources.json` | every pin + sha256 of the committed blob |

`ACCURACY.md` (this lab) maps every number to file:line.

## What changes the script

1. **Claude never made the mistake.** 6 of 6 runs rounded first (3 of 3 without being told). So: the JSON 1 VO uses the
   **no-AI variant** ("This is the message, written the way Claude writes it. We sent it ourselves, hollow first."); the
   hook never implies Claude erred; chapter 7 says "Claude rounded first 6 times out of 6, 3 of them without being told",
   and the line "so say the order in your prompt" is **not** allowed (the named arm did no better). The trap the video
   warns about is in the tool's offer (6.82 mm → 0.0035 mm), not in Claude.
2. **JSON 2 source is the lab's no-AI `set_parameter`** (no agent run sent one). VO names it as our test.
3. **JSON 1 is two cards** (shell step; fillet step's params): the whole fillet step is 14 rows at 44 columns.
4. **"You can download this file and run it" is allowed** (A9): the CLI builds one file and refuses the other at "step 6"
   (it counts from 1; the batch reply's `index` counts from 0).
5. **Chapter 6 number:** 0.0035 mm ("far thinner than a sheet of paper"); GO-B hook "about a third of a millimetre" (0.3431).
6. **Outro:** "Next: screw bosses, and a lip for the lid." Not "a lid that fits" (the lid is untested).
7. `rolled_back: true` comes from the batch reply; with the step file the reply also says `undone: 5`.

## Open (owner)

- Budget left: $9.76 of $10. Not spent: the plan defines 6 runs. A third arm that forces the trap ("hollow it out first,
  then round the corners") would show what Claude does after the refusal (reorder? take 6.82?), which is the most
  interesting chapter-7 beat, but it is not in the reviewed plan: it needs a plan amendment and a reviewer before any spend.
- Slicer beat (producer SF1), a printed box (SF2), schedule swap with HikariCP (SF6).
- Publish: lab goes public on thestackunderflow when the video ships (local commits only until then).

## Video (21 Oct 2026, ~08:00)

Rendered and kitted: PUBLISH/51-solidcraft-fillet-shell (6:52 + a 35 s Short), primer `mcp-canvas/primers/solidcraft-fillet-shell.primer.json`
(ce5a576), cards pinned at f384450. Hook stills `video/frames/hook-landscape.png` / `hook-vertical.png` from `video/make_hook.sh`
(words only on SolidCraft's renders; "red: edges highlighted by us"). Release Fri 30 Oct; this repo goes public then (owner's yes).
