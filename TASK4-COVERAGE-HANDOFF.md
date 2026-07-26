# Task 4 (coverage) — work-in-progress handoff

Written 2026-07-22 mid-task so a session end loses no context. This is a
scratch continuity note, not a deliverable; delete it once Task 4 lands.
The CODE below is all saved to disk and survives; this file preserves the
reasoning and the exact resume steps.

## Where things stand

- Fork CONFIRMED Case 1 (dormers exist in raw, segmentation dropped them).
- Emmett OVERRODE the original area-ownership rule in favour of the
  evidence-adjusted rule (see gate finding below).
- Coverage code is WRITTEN and the recovery step is VERIFIED working.
- The full end-to-end run was KILLED before finishing (session wind-down),
  so its comparison JSON and the final area/decomposition numbers do NOT
  exist yet. **First resume action: re-run it (command below).**

## Resume command (writes reports/big_house/coverage-comparison-<date>.json)

```
.venv/Scripts/python.exe scripts/coverage_recon.py C:/odm/datasets/big_house
```

Heavy (~10-15 min: three 9M-pt facet assignments + alpha rasterization over
26 facets). NEXT TIME launch it unbuffered so progress is watchable:
`.venv/Scripts/python.exe -u scripts/coverage_recon.py ...` (and consider
adding flushed stage markers to the script).

## Files written this task

- `roofkit/coverage.py` — NEW module. Completeness gate: plan_grid,
  coverage_masks, residual_blobs, calibrate_quality_bar, recover_facets
  (relax SIZE, hold QUALITY), facet_kept_alpha + area_accounting
  (gross/occluded/net, highest-surface-wins), pairwise_matrix, coverage_fraction.
- `scripts/coverage_recon.py` — full end-to-end run (main facets ==
  freeze, quality bar, coverage, threshold sweep, recovery, matrix, area
  accounting, decomposition vs frozen 313.188, writes a NEW comparison file).
- `scripts/diag_coverage.py` — diagnostics: modes explore/spacing/dormer/
  residual/doublecheck. All Task 1-3 evidence + the double-count gate.

## Verified findings (evidence for the DECISIONS entries)

Task 1 — spacing (big_house): median NN on a clean single-facet tile 0.0041 cu
(whole roof.npy 0.0052). Coverage cell = 2.5 x 0.0052 = 0.013 cu.

Task 2 — dormer fork: residual (roof.npy pts beyond band of every accepted
facet) = 19.1% of roof.npy, RAW roof-band density in dormer cells == clean
main roof (median 9 pts/cell each, ratio 1.00). Residual is by construction
IN roof.npy, so dormers survive crop/height/color/planarity; only the
facet-acceptance step (min_points_frac) drops them. CASE 1.

GATE — double-count: only 8.9% (2.87 of 32.4 cu^2) of dormer plan area sits
inside any accepted facet's counted alpha surface; the five real dormers
overlap host area only 5-14% (biggest blob 0%). So parents ALREADY leave the
holes open. => original "subtract full child footprint" rule OVER-corrects.
Adjusted rule (Emmett approved): gross = alpha area (holes open); occluded =
only the counted overlap where a higher facet also covers, at parent pitch;
net = gross - occluded.

Recovery (verified on the killed run's early stage): 8 main -> 18 recovered.
Five clean dormers are GABLED, each giving two opposing faces (10 facets);
plus blob 0 (the 5.94 cu^2 triangle, 2 planes), a 6th lower dormer (blob 7),
and small ones. **Hard rule works: blob 8 (RMS 7.4x spacing) was REJECTED on
quality; dormers passed with relaxed size.** Quality bar = 2.95x spacing
(worst main facet). Pre-recovery coverage 83.6%.

## Still OPEN (produce on re-run)

- Post-recovery coverage % (should climb well above 83.6%); where remaining
  residual sits (seams/perimeter vs missing facets).
- Threshold plateau sweep: confirm 5-dormer plateau is flat (known answer:
  5 visually-confirmable dormers; but gabled => 10 faces, so expect the
  face-count plateau, reconcile the two framings).
- Pairwise matrix: is blob 0's triangle a real facet or over-segmentation?
  (angle<2deg AND offset<0.10cu = coplanar => merge later). REPORT ONLY.
- Area accounting numbers + decomposition: new_total_net = frozen 313.188 +
  dormer_gross - occlusion. Must reconcile line-by-line.
- Merge operation + scale: STILL DEFERRED, do not touch.

## DECISIONS.md drafts (SHOW Emmett before writing; do not write yet)

Entry 1 (goal reframe) ALREADY EXISTS in DECISIONS.md (2026-07-21). Do not
duplicate.

Entry 2 — "Coverage replaces expected_facets as the completeness gate."
REVERSES two standing decisions: expected_facets pinned at 8 as vanish
guard, and "dormer detection deferred until after the three houses." Per the
reversal-propagation rule, sweep + update: DECISIONS current-state block,
CLAUDE.md (if it names expected_facets), and memory
`replication-houses-context.md` (dormers-after-three-houses). Draft Why:
expected_facets is a human magic number that blocks automation and cannot
catch an unexpected facet; the closed-surface invariant needs no prior
count. Hard rule (relax size, never fit-quality) keeps it honest: a small
patch of anything is planar, so relaxing RMS fits noise. Evidence: Task 1-3
+ gate above + recovery (blob 8 rejected on quality). Rejected: keep
expected_facets (magic number); alpha/concave-hull completeness (its own
magic shape param); relax quality to force 100% (fits noise).

Entry 3 — "Dormer area ownership: highest surface wins; big_house total
restated." Why/Rejected can be written now; EVIDENCE NEEDS THE RE-RUN
NUMBERS (frozen 313.188 vs new net, decomposition). Adjusted rule per the
gate (parents already leave holes open, so subtract only counted overlap).
This restates big_house's total as the pipeline improving WITH decomposition,
never as a regression; frozen file stays untouched, new comparison file only.

## Guardrails still in force

- io.py stays the only format-aware module. Scale handling untouched.
- Frozen files never edited. Comparison goes in a NEW file.
- Freeze/commit are Emmett's deliberate acts: generate and show, never commit.
