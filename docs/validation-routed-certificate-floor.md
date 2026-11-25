# Measure the cost floor of narrow routed validation

The previous replay preserved every uncapped nomination and qualification reply by changing only validation read order. It found no pooled savings. This audit replays the original routing and asks how many of its uniform validation replies could be skipped if the useful grades were already known. It covers the same 824 recorded AIME, ARC-AGI, GSM8K, and SST5 episodes. The published baseline lookup counts, holdout passes, ARC-AGI prices, and math layouts all reproduced. [Exact-order replay](validation-routed-exact-order.md) · [Sealed floor audit](validation-routed-certificate-floor-v1.json)

Both floors preserve the exact full-panel nominee and roster order on ties. A certificate gives the winner a lower bound of `s` passes. Each earlier rival then needs at least `n − s + 1` observed misses on an `n`-case panel, and each later rival needs `n − s`. The calculator tries every feasible `s` and finds the cheapest sufficient subset of recorded replies. It includes any already-paid routing grades. When the **complete-score floor** has a challenger nominee, it also requires every incumbent and nominee reply because the current qualification planner uses both full scores. The **nominee-only floor** drops that requirement. The audit holds nonuniform validation and all qualification charges fixed for both calculations.

| Archive | Uncapped lookups | Complete-score floor | Stall-only lookups | Nominee-only floor |
| --- | ---: | ---: | ---: | ---: |
| AIME, original | 601 | 545 | 533 | 467 |
| AIME, rotated | 4,658 | 4,219 | 4,125 | 3,637 |
| ARC-AGI, original | 774 | 739 | 610 | 561 |
| ARC-AGI, rotated | 3,212 | 3,117 | 2,914 | 2,757 |
| Promptolution GSM8K | 850 | 832 | 768 | 742 |
| Promptolution SST5 | 1,598 | 1,516 | 1,336 | 1,259 |

Even with hindsight, exact reordering under the current full-score requirement cannot reach the stall-only lookup count in any group. On the original ARC-AGI start, only 35 of 774 lookups could be removed while preserving the full scores and all other charges. That leaves the complete-score floor 129 lookups above stall-only, which scored 35 fewer passes than uncapped routing. Eighteen of the 37 original-start uniform screens were already at the complete-score floor. At recorded ARC-AGI prices, the original-start floor is $69.05, compared with $73.64 for uncapped routing and $58.62 for stall-only. The rotated floor is $399.56, compared with $416.67 and $380.11.

The nominee-only bound falls below stall-only in every group. On original-start ARC-AGI it falls to 561 lookups and $54.45 at recorded prices. This identifies the full-score requirement as a material constraint. The bound uses unseen replies to choose a certificate and keeps qualification charges fixed. A practical selector would have to find its certificate without those grades, and changing the scores supplied to qualification can also change its lookup cost. [Runner](../benchmarks/validation_routed_certificate_floor.py) · [Exhaustive certificate test](../tests/unit/test_validation_routed_certificate_floor.py)

## Reproduce offline

Use Python 3.12, the pinned GEPA 0.1.4 wheel, and the Promptolution corpus from the original comparison. Run the benchmark without arguments to preview its seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.validation_routed_certificate_floor \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute b6365401f506d5883298aa93f3ce5e87412bce9df4e2a96f696f2ef1c9d7350b \
  --out NEW_REPORT.json
```

Two socket-blocked replays matched byte for byte at SHA-256 `6a7194d43269da853d4c91d45e390c406a8d47af2d1b7313f3d87d1ac6a6b599`. All 50 focused tests and four subtests passed. The weighted certificate test checked every paid subset and possible completion on all 64 two-case Boolean panels with three prompts. The CLI refused a stale seal and an existing output path. Zero provider requests were sent. Storage Guard measured 9.1 GiB free. The source export, pinned wheel overlay, corpus copy, and publication worktree used 123 MiB under the standing LAB exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
