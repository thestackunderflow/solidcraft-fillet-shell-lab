# ACCURACY: every number the video may say, mapped to a lab file and line

Lab: `solidcraft-fillet-shell-lab`, card sources pinned at commit **f384450** (`video/panel-sources.json`, sha256 of each
committed blob). SolidCraft **0.17.0** unless a row says otherwise. Paths are relative to the lab root. Line numbers are of
the pinned commit. `tests/test_evidence.py` re-derives `out/evidence/numbers.json` from these files on every run.

## The refusal and the fix (GO-A)

| # | Claim (as it may be said / shown) | Value | File:line |
|---|---|---|---|
| A1 | Shell first, then a 10 mm fillet on the 4 vertical edges is refused | `ok: false`, `isError: true`, `failed.command` `solid.fillet` | `out/probe/0.17.0/SF-10-1/batch2_reply.json:2-9`; 3/3 repeats `SF-10-{1,2,3}` |
| A2 | The refusal text (verbatim) | `fillet: the rounds would leave openings in the surface (they overlap where a wall or a face is narrower than both); the largest radius that fits is 6.82 mm` | `out/probe/0.17.0/SF-10-1/batch2_reply.json:7`; `out/evidence/refusal.txt:1` |
| A3 | "It undid the whole batch" | `rolled_back: true` (batch reply, not `inspect_design`) | `out/probe/0.17.0/SF-10-1/batch2_reply.json:12`; step-file batch: `undone: 5`, `out/steps/batch-replies.json` (shell-then-fillet entry) |
| A4 | The step it refused is step 5 counting from zero (the sixth) in the step file | `failed.index: 5` | `out/steps/batch-replies.json:9` |
| A5 | Round first, then shell (R10) builds | `ok: true`, `completed: 6` (step file); timeline `Sketch1, Extrude1, Fillet1, Shell1`, all `error: null` | `out/steps/batch-replies.json` (fillet-then-shell entry); `out/probe/0.17.0/FS-10-1/summary.json` (`timeline_after`) |
| A6 | Volume of the R10 box (SolidCraft `measure`) | 23 795.10 mm³ | `out/probe/0.17.0/FS-10-1/summary.json:92` (23795.100152624625) |
| A7 | Hand count for it (G1, `shelled_volume`) | 23 795.04 mm³; match +0.0002% | `out/probe/0.17.0/FS-10-1/summary.json:255`, `:258`; formula `tests/measure_box.py` (`shelled_volume`) |
| A8 | The wall is 2 mm all the way round (R10 and R6, round first) | 2.0000 mm (STL circle fit); SolidCraft radius − axis 2.0000 | `out/probe/0.17.0/FS-6-1/stl_measure.json:21`; `FS-10-1/stl_measure.json:21`; `FS-6-1/summary.json` (`radius_minus_axis_mm`) |
| A9 | "You can download this file and run it": `solidcraft-cli run` builds the round-first file and refuses the shell-first one, writing nothing | exit 0 + STL (wall 2.0000) / exit 1, "error: step 6 (solid.fillet): … 6.82 mm", no file | `out/steps/run-fillet-then-shell.json:9`, `out/steps/run-fillet-then-shell-measure.json:21`; `out/steps/run-shell-then-fillet.json:11` |

Note A4 vs A9: the batch reply counts from 0 (`index: 5`), the CLI from 1 ("step 6"). Same step.

## It builds, but (GO-B) and the offered radius

| # | Claim | Value | File:line |
|---|---|---|---|
| B1 | Shell first, then a 6 mm fillet builds with no warning | `ok: true`, `warning: null` | `out/probe/0.17.0/SF-6-1/batch2_reply.json:19`; 3/3 |
| B2 | Its corner wall | 0.3431 mm (STL fit); 0.3431 (SolidCraft radius − axis, 0.34314575…); SolidCraft two-item `min` 0.3413 | `out/probe/0.17.0/SF-6-1/stl_measure.json:21`; `SF-6-1/summary.json:231`, `:230` |
| B3 | The radius SolidCraft offered builds too, with no warning | R 6.82, `ok: true`, `warning: null` | `out/probe/0.17.0/SF-offered-1/summary.json:4`; `SF-offered-1/batch2_reply.json` |
| B4 | Its corner wall | 0.0035 mm (STL); 0.0035 (radius − axis, 0.00349…) | `out/probe/0.17.0/SF-offered-1/stl_measure.json:21`; `SF-offered-1/summary.json:231` |
| B5 | Hand geometry predicted both (G2, R − (R − 2)·√2) | 0.343, 0.0035 | `tests/test_measure.py` (`g2`), `out/probe/SUMMARY.md` (expected-wall column) |

Spoken analogies (never on screen as numbers): 2 mm ≈ a coin, 10 mm ≈ a fingertip, 0.34 mm ≈ three sheets of paper,
0.0035 mm ≈ far thinner than a sheet of paper.

## Six tries with Claude

| # | Claim | Value | File:line |
|---|---|---|---|
| C1 | Runs, arms | 6: plain 3, named 3, alternating | `out/runs/SCORES.json:4,58,112,164,216,268` |
| C2 | Rounded first | plain 3 of 3, named 3 of 3 | `out/runs/SCORES.json:26,80,132,184,236,288` (`first_attempt_order: FS`) |
| C3 | Refusals | 0 | `out/runs/SCORES.json` (`refusals: 0` in each run) |
| C4 | Parts in spec (bbox ±0.1, volume ≤0.5%, wall ≥1.9) | 6 of 6; wall 2.0000, volume −0.0258% vs hand count (STL) | `out/runs/SCORES.json` (`scored: pass`, `part`) |
| C5 | Total cost "at API prices" | $0.2377 (each $0.0328-$0.0562) | `out/runs/BUDGET.log:6`; `out/runs/SCORES.json:320`; per run `:10,64,118,170,222,274` |
| C6 | Model, Claude Code version (stamp only) | `claude-sonnet-5-5`, 2.1.303 | `out/runs/*/run-meta.json` |
| C7 | The reports were true | 6 of 6 quote SolidCraft's `measure` volume (23,795 mm³) and "no step failed"; plain-2 also mentions a first call to a tool name that does not exist, which never reached the MCP server (not verifiable from the MCP log) | `out/runs/SCORES.json` (`final_text`), `out/runs/*/transcript.jsonl` |

## Versions (lab README / pinned comment only)

| # | Claim | File:line |
|---|---|---|
| V1 | 0.16.2 refuses SF-6: "not supported yet: 6 mm is too large for this fillet: it runs past the faces beside the edge into other geometry; the largest radius that fits is 4 mm" | `out/probe/0.16.2/SF-6-1/batch2_reply.json:7` |
| V2 | 0.18.1 = 0.17.0 on every deciding cell (SF-6 wall 0.3431, SF-10 refused with 6.82 mm) | `out/probe/0.18.1/SF-6-1/summary.json:105`; `out/probe/SUMMARY.md` |
| V3 | SF-7 offers "6.828 mm" (more digits than SF-10's "6.82 mm") | `out/probe/0.17.0/SF-7-1/batch2_reply.json:7` |
| V4 | `fit: "reduce"` / `"taper"` do not rescue SF-10 (same refusal) | `out/probe/0.17.0/SF-fit-reduce-1/batch2_reply.json:7`, `SF-fit-taper-1/batch2_reply.json:7` |
| V5 | 0.17.0 `tools/list` includes `describe_command` (no count said) | `out/probe/0.17.0/interface/tools_list.json:47` |

## Part 4 (outro wording)

| # | Claim | File:line |
|---|---|---|
| P1 | 4 screw bosses build on the R10 box's floor (`completed: 4`), +1 611.33 mm³ (hand count 1 611.68) | `out/probe/0.17.0/P4-1/summary.json:6-11` |
| P2 | A lip builds on the rounded rim (`plastic.lip`), +506.81 mm³ | `out/probe/0.17.0/P4-1/summary.json:91`; render `P4-1/lip.png` |
| P3 | The lid itself (second body, clearance) is **not** tested | — |

## Not measured here (do not say)

Printability or slicer behaviour; the fillet radius as a measured value beyond the circle fit (r_fit 10.0 / 6.0 / 6.82 is in
`stl_measure.json`, and `body_topology` cylinder radius in `body_topology.json`: allowed only as "the round is 10 mm" if
both are quoted); anything about other CAD tools; the chat panel's tool list.
