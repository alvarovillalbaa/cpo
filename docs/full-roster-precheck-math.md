# Transfer CPO’s full-roster precheck to AIME and ARC-AGI

The roster-width guard was chosen on archived language and Promptolution results. This transfer runs the published opt-in API on AIME and ARC-AGI without changing the guard. Across 1,520 one-cycle trials, the replay keeps the original starts, ordered rosters, seeds, validation, training and holdout splits. It uses the first two training cases for CPO's opening probe and the first four original admission cases for every arm. AIME already uses four admission cases. ARC-AGI originally uses six. The recorded prompt pools support one cycle per trial. [Published API](full-roster-precheck.md) · [Original math layout](recorded-math-router-transfer.md) · [Transfer benchmark](../benchmarks/full_roster_precheck_math.py)

## Paired feedback results

| Archive and setting | Packaged passes / lookups | Opt-in passes / lookups | Lookups saved | Best affordable GEPA or retention |
| --- | ---: | ---: | ---: | ---: |
| AIME, root, four | 497 / 536 | 497 / 519 | 17 | 501 / 514 |
| AIME, root, eight | 490 / 482 | 490 / 448 | 34 | 500 / 0 |
| AIME, rotated, four | 4,035 / 3,992 | 4,035 / 3,881 | 111 | 4,067 / 2,857 |
| AIME, rotated, eight | 4,045 / 3,779 | 4,045 / 3,556 | 223 | 4,067 / 2,857 |
| ARC-AGI, root, four | 1,405 / 621 | 1,405 / 619 | 2 | 575 / 0 |
| ARC-AGI, root, eight | 1,277 / 574 | 1,277 / 569 | 5 | 575 / 0 |
| ARC-AGI, rotated, four | 13,563 / 3,079 | 13,563 / 2,750 | 329 | 13,374 / 2,615 |
| ARC-AGI, rotated, eight | 13,449 / 2,901 | 13,449 / 2,485 | 416 | 13,372 / 2,463 |

Every trial reproduced the packaged nominee and final prompt. Archival lookup spending fell from 15,964 to 14,827, a 7.1% saving over the measured mix. The opt-in runner was cheaper in 622 trials, costlier in 86, and tied in 812. ARC-AGI's archived evaluator prices put the replayed saving at $92.34 across its four configurations. The same physical case can occur in multiple trials, and this design verifies opening-cycle transfer. [Counts, traces, and matched controls](full-roster-precheck-math-v1.json)

Each comparison sweeps the original split-safe GEPA settings through cap 180, repriced on the four-case qualification panel. It then replays the best setting affordable at the opt-in runner's realized lookup count. The opt-in runner led both rotated ARC-AGI configurations by 189 and 77 passes, with paired case ranges of +139 to +239 and +43 to +110. On the ARC-AGI root configurations the affordable comparison was retention. All four AIME comparisons favored GEPA or retention by point estimate, with paired ranges crossing zero. The transfer confirms an archived lookup improvement over packaged feedback. Live superiority remains unverified.

## Reproduce offline

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel. The benchmark loads the reduced math corpus from the repository.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.full_roster_precheck_math \
  --execute 999bfe82cb008e3d245ec8a1c2ac019d4dc09458c829f4164343bb49fa2ee5e6 \
  --out /tmp/cpo-full-roster-math.json
```

Two network-disabled replays produced byte-identical receipts. All 81 focused tests passed, including trial geometry, original proof eligibility and per-reply price reconciliation. Storage Guard measured 8.8 GiB free. The source export, pinned wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. Teardown was verified. [Tests](../tests/unit/test_full_roster_precheck_math.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
