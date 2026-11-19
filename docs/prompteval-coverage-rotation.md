# Spread first-gain probes across validation misses

The reachability audit found that a different prompt sequence could match the GEPA score under the existing validation and qualification gates in most losing comparisons. The first-gain baseline visits challengers in proposal order and probes each on the same missed case. This study changes how the optimizer allocates those first probes and which challenger it certifies. [Reachability audit](prompteval-gate-reachability.md) · [First-gain baseline](single-finalist.md)

| Policy | Probe and nomination rule |
| --- | --- |
| Rotate misses | Assign each successive challenger the next incumbent miss in seeded order, wrapping as needed. Stop at the first observed gain. |
| Retention duel | Use the first incumbent miss for every gain probe. If the first nominee fails a case the incumbent passed, look at up to three later challengers for one that passes both probes. Prefer a critical case for this retention check when one exists. |
| Rotate and duel | Rotate the gain probes and use the same retention check and lookahead. |

The search reserves enough lookups for a full certificate before starting a new challenger. If the retention check finds no replacement, the first nominee keeps its place and its paid replies. All policies certify at most one challenger. The certificate requires a strict validation gain and preserves critical incumbent passes. An independent qualification gain is still required before promotion. The original four-cycle proposal stream, archive policy, 12 validation rows, cap of 52, and eight qualification rows per cycle apply to all 18 panels. The runner verifies the archived first-gain selection trace and checks that both official GEPA control traces match across all policies. [Benchmark runner](../benchmarks/prompteval_screen_coverage_rotation.py)

## Results

Each cell reports final holdout passes and paid lookups. The last column counts panels meeting both measured GEPA gates.

| Policy | Development | Finalist transfer | Retrospective transfer | Both GEPA gates |
| --- | ---: | ---: | ---: | ---: |
| First-gain | 4,149 / 14,775 | 4,455 / 21,833 | 10,187 / 29,873 | 4 / 18 |
| Rotate misses | 4,130 / 16,603 | 4,450 / 23,955 | 10,265 / 33,511 | 0 / 18 |
| Retention duel | 4,146 / 14,930 | 4,455 / 21,913 | 10,186 / 30,256 | 2 / 18 |
| Rotate and duel | 4,132 / 16,757 | 4,450 / 24,051 | 10,264 / 33,771 | 0 / 18 |
| Sequential GEPA | 4,128 / 21,574 | 4,483 / 31,157 | 10,219 / 43,164 | — |
| Batched GEPA | 4,150 / 15,311 | 4,466 / 22,028 | 10,244 / 30,632 | — |

Rotating the misses gained 54 aggregate passes and added 7,588 lookups against first-gain. It improved eight panels and lost passes on ten. Most of the gain came from retrospective transfer, where rotation scored 21 more passes than batched GEPA and spent 2,879 extra lookups. Across the three cohorts it scored 15 more passes than sequential GEPA and used 21,826 fewer lookups, while finishing 15 passes below batched GEPA at 6,098 extra lookups.

The duel changed the initial nominee in 24 cycles with shared probes and 13 with rotation. Adding the duel to rotation gained one aggregate pass and added 510 lookups. With shared probes, the duel lost four aggregate passes and added 618 lookups against first-gain.

The gate requires at least as many holdout passes at equal or lower cost against each control, with at least 10% savings on a score tie. The pooled gains show that spreading probes can improve accuracy under the same strict promotion rules. The panel losses and extra lookups also show why rotation stays benchmark-only. The replays reuse final holdout cases across seeds, and all three replay phases reproduced byte for byte. [Per-panel results and seals](prompteval-coverage-rotation-results-v1.json)

A follow-up delayed incumbent reads while preserving each cycle's decisions. The shared first-gain screen saved 20.1% of paid lookups, while rotation with the eager proof order used the same number. [Deferred incumbent reads](lazy-incumbent.md)

## Reproduce

Use pinned GEPA 0.1.4. Preview each phase to obtain its seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_screen_coverage_rotation --phase finalist-transfer
```

The other phases are `development` and `retrospective-transfer`.
