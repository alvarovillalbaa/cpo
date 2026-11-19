# Qualifying archived prompts before search

Trying archived finalists first skipped proposal search on 190 of 220 outage splits. CPO gained 101 replay passes and used 3,873 fewer calls than its diverse-panel baseline. GEPA with the same archive made the same outage selections. CPO spent fewer calls, with savings below the 10% threshold for an accuracy tie. [Seals and results](recorded-archive-first-results-v1.json)

## Protocol

Each task uses the existing 220 three-case holdouts and the same diverse validation and promotion panels. Archive candidates are the historical finalists from the strict, field-guided, and hybrid runs, in that order. Duplicate prompts and the incumbent are skipped. This makes one or two earlier prompts available per task. All three optimizers receive the same archive. The preflight uses only the current promotion rows. It accepts the first challenger that proves a strict exact gain while preserving the incumbent's critical passes. Search runs when no candidate qualifies. [Prior diverse-panel replay](recorded-promotion-strata.md) · [Archive reuse experiment](recorded-outage-specialists.md)

The full-panel variant requires the accepted archive prompt to pass every promotion case. The withheld-source variant removes the field-guided run from the archive. The validation-first variant measures incumbent validation before consulting the archive. A perfect incumbent skips the archive, matching the observed search exit. The benchmark added that variant after finding the preflight wasted calls on ticket. It remains exploratory.

Archive retrieval uses one proposal slot. An early implementation exceeded the original maximum in a fallback. The final replay deducts preflight lookups from the remaining evaluation and proposal budgets before rerunning fallback search for every method. Qualification reuses matching incumbent or challenger observations. The recorder verifies the original combined caps for every arm and split. Validation-first also charges incumbent validation when it skips proposal search.

## Results

Each cell gives exact passes and charged calls. The fixed outcomes reuse 12 source cases per task across the 220 splits.

| CPO policy | Ticket | Warehouse | Outage |
| --- | ---: | ---: | ---: |
| Diverse-panel baseline | 660 / 660 | 605 / 1,808 | 507 / 6,345 |
| Archive-first | 660 / 1,320 | 605 / 2,561 | 608 / 2,472 |
| Require a full archive panel | 660 / 1,320 | 605 / 2,561 | 608 / 2,550 |
| Withhold the field-guided archive | 660 / 1,320 | 605 / 2,489 | 506 / 6,824 |
| Validation-first | 660 / 660 | 605 / 1,808 | 557 / 2,791 |

Full-panel qualification kept the archive-first selections. It added 78 outage calls. Withholding the field-guided archive eliminated every search bypass and the outage gain. Validation-first restored the original ticket and warehouse cost and quality. On outage it saved 3,554 calls and gained 50 passes over standard CPO. Compared with archive-first, it lost 51 outage passes and 14 matched critical passes. Equal observed validation scores alone can hide a better archived prompt.

The original provider panel has replies for one of the two different outage prompt pairings between archive-first and standard CPO. That observed pair gained nine passes with no matched critical loss. The other pair is missing 18 replies. Against GEPA with matched archive-first or validation-first, CPO tied on outage quality and fell short of the required call savings. Warehouse validation-first used 738 fewer calls at the same quality against either GEPA variant. The history built the proposal bank, and the replay compares selection on that bank. A fresh model-backed result is still required.

## Reproduce offline

Use the intact research archive and pinned GEPA 0.1.4. Preview to obtain the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_archive_first \
  --replay FULL_PROMOTION_REPLAY.json \
  --source-plan REWRITE_FIRST_PLAN.json \
  --archive ORIGINAL_OPEN_EVALS_STUDY
```

Both offline runs reproduced every task's original diverse-panel totals and returned identical reports. [Runner](../benchmarks/recorded_archive_first.py) · [Tests](../tests/test_recorded_archive_first.py)
