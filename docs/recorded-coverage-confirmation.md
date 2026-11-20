# Early coverage rejection on recorded model replies

The scripted benchmark showed that rejecting impossible coverage during confirmation can free enough budget to find a better candidate. This replay tests the same mechanism on archived GPT-6.2 Sol outcomes. It includes 23 ticket prompts, 21 warehouse prompts, and 27 outage prompts with complete recorded development evidence. [Scripted benchmark](joint-coverage-confirmation.md) · [Recorded archive provenance](recorded-replay.md)

## Protocol

Each task enumerates all 220 three-case holdouts from its 12 recorded development cases. A seed assigns the other cases to three training, four validation, and two qualification slots and shuffles the reachable prompt roster. CPO and both official GEPA 0.1.4 modes have the same starting prompt, roster, and paid search caps of 24 and 36. GEPA can evaluate training cases and receives field credit bounded below one full pass per panel. All methods use the same independent matched qualification.

CPO requires an exact validation improvement and preserves the original incumbent's critical passes. The exact-only arm stops once those conditions cannot be met. The late-coverage arm also requires one pass per critical policy stratum after an exact score. Coverage-first uses the same gate and checks whether a required stratum has no possible pass while evaluating the candidate. Strata use only policy inputs and critical-case declarations. Lookup totals count search and qualification. The supplied archive roster has no proposal generation charge. [Runner](../benchmarks/recorded_coverage_confirmation.py) · [Policy strata](recorded-promotion-strata.md)

## Results

Cells show replay holdout passes / paid lookups. Each task reuses 12 actual cases to produce 660 holdout observations per cap.

| Task and cap | Exact-only CPO | Late coverage | Coverage first | Sequential GEPA | Batched GEPA |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ticket 24 or 36 | 660 / 880 | 660 / 880 | 660 / 880 | 660 / 880 | 660 / 880 |
| Warehouse 24 | 605 / 2,053 | 605 / 2,053 | 605 / 2,053 | 605 / 1,944 | 605 / 1,336 |
| Warehouse 36 | 605 / 2,321 | 605 / 2,321 | 605 / 2,321 | 605 / 2,856 | 605 / 2,248 |
| Outage 24 | 458 / 4,293 | 454 / 4,264 | 457 / 4,166 | 396 / 3,784 | 389 / 2,251 |
| Outage 36 | 483 / 5,557 | 475 / 5,532 | 485 / 5,253 | 421 / 5,845 | 406 / 4,657 |

Coverage-first gained three and ten outage passes against late coverage while saving 98 and 279 lookups. It lost zero matched critical cases to late coverage at either cap. At cap 24 it lost one matched critical pass to exact-only CPO and paid more lookups than both GEPA modes. At cap 36 it had one matched critical loss against batched GEPA and two against sequential GEPA. The strata for all three loss observations were absent from the critical rows of both validation and qualification. Batched GEPA also used 596 fewer lookups. The zero-critical-loss and cost gate against both GEPA controls remains unmet.

The separate original provider holdout covered only two of six distinct directed outage comparisons against each GEPA control at cap 36. Across those observed directions, the net pass delta was zero and four critical losses were recorded in each comparison. These are repeated comparisons on the same limited provider case bank. They cannot establish the missing directions or fresh candidate performance. [Sealed totals and holdout coverage](recorded-coverage-confirmation-results-v1.json)

A follow-up tested reallocating cases across training, validation, and qualification. It found that all three critical loss observations came from conditions missing from the entire development split. [Critical case allocation replay](recorded-critical-allocation.md)

## Reproduce

Use the intact GEPA research archive, its original Open Evals source study, and the pinned GEPA 0.1.4 wheel. Preview and run from the CPO checkout.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_coverage_confirmation
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_coverage_confirmation \
  --execute 851b71ea69a92a6347d659b3da1cf28d0eb18eb004a4d263062576af057f4be8 \
  --out NEW_REPORT.json
```

Two exact-source replays matched byte for byte with sockets and DNS blocked. The loss-attribution pass preserved the original selections, costs, and trace digests. Eight focused tests passed. The CLI rejected the wrong seal and an existing output path. Storage Guard measured 17.8 GiB free. The 18.6 MB temporary source and wheel overlay was removed under the standing LAB exception. [Verification receipt](recorded-coverage-confirmation-verification-v1.json)
