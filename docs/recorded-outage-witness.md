# A reserved check for long outages with missing evidence

The diverse-panel replay left four matched critical loss observations against GEPA. Three reused one case involving a long outage with missing evidence. In those splits, that policy condition was absent from all nine training, validation, and promotion cases. The incumbent also failed all four held-out observations. [Diverse panel results](recorded-promotion-strata.md)

This follow-up reserved all three long outages with missing evidence from the original provider holdout. It selected the first case the incumbent had passed, `outage-holdout-11`, using two incumbent lookups in case order and no challenger outcomes. The other 15 cases stay outside the analysis. The same rule applies to CPO and both GEPA controls. When the condition was absent from all development cases and promotion would otherwise succeed, the arm checks its challenger on the reserved case. A failed check retains the incumbent.

The rule triggered on 34 of CPO's 220 splits. Twenty-one had recorded passing replies and thirteen depended on missing replies. Across CPO and both GEPA controls those gaps reduce to two distinct prompt-and-case replies. The replay enumerated all four possible binary assignments. Each assignment applies the same missing result wherever its prompt reappears.

| Result across possible replies | CPO | Sequential GEPA | Batched GEPA |
| --- | ---: | ---: | ---: |
| Replay passes out of 660 | 497–507 | 430–433 | 430–432 |
| Charged calls | 6,379 | 7,282 | 7,531 |
| Additional challenger lookups | 34 | 12 | 15 |
| Critical passes lost by CPO | | 1 | 3 |

The call totals exclude the two shared incumbent lookups used to pick the reserve. The replay checks that each split can fund a fresh incumbent and challenger pair within the original combined evaluation cap. The matched critical-loss counts stayed at one and three in every completion. Even if this witness vetoes a challenger, the incumbent does not repair the target cases in this archive. A fallback that can pass those cases would have to be evaluated on its own evidence. [Machine-readable result](recorded-outage-witness-results-v1.json)

This is a retrospective check prompted by the recorded failures. The ranges describe the original replay, and the remaining provider holdout stays unscored for this policy. No witness request was sent.

## Reproduce offline

Use the intact research archive and pinned GEPA 0.1.4. Preview to obtain the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_outage_witness \
  --replay FULL_PROMOTION_REPLAY.json \
  --source-plan REWRITE_FIRST_PLAN.json \
  --archive ORIGINAL_OPEN_EVALS_STUDY
```

Both runs reproduced the source baseline and produced identical reports. Tests cover witness selection, missing replies, and shared reply assignments across arms. [Runner](../benchmarks/recorded_outage_witness.py) · [Tests](../tests/test_recorded_outage_witness.py)
