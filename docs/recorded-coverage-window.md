# Screen small challenger groups with one shared validation case

The recorded coverage frontier found an outage accuracy advantage at higher realized lookup cost. This follow-up tests whether a cheap shared probe can improve candidate order under the existing budget. The two variants retain the same archived candidate roster, validation, independent qualification, and holdout. Both retain the previously measured incumbent qualification precheck. [Realized-cost frontier](recorded-coverage-frontier.md)

The selector reads the incumbent on the full validation panel. It picks a case the incumbent failed, preferring a critical case in the smallest represented stratum. It measures that case on up to four consecutive challengers while reserving the budget to complete one candidate. The binary policy ranks exact passes first and retains proposal order on a tie. The field policy breaks those ties by matched fields. Both reuse each probe during exact confirmation. A candidate must still improve the exact validation score, preserve protected critical passes, and pass a case in every represented critical stratum. [Runner](../benchmarks/recorded_coverage_window.py)

## Results

Cells report outage holdout passes out of 660 and realized lookup counts. The 220 holdouts reuse 12 physical cases.

| Search cap | Unscreened CPO | Binary screen | Field tie-break |
| --- | ---: | ---: | ---: |
| 24 | 457 / 3,324 | 483 / 3,314 | 483 / 3,316 |
| 36 | 485 / 4,059 | 515 / 3,784 | 515 / 3,783 |
| 48 | 512 / 4,313 | 518 / 3,855 | 518 / 3,855 |

The binary screen gained six passes and saved 458 lookups at cap 48 against unscreened CPO, with zero matched critical losses. Matched-field tie-breaking yielded the same total holdout passes at each cap and changed cost by at most two lookups. Ticket retained 660 passes with 440 paid lookups, and warehouse retained 605 with 537, across all three CPO policies. [Full results and paired comparisons](recorded-coverage-window-results-v1.json)

The previous frontier used sequential GEPA at cap 32 as the fixed reference for unscreened CPO at cap 48. GEPA scored 410/660 with 4,016 lookups. Screened CPO at cap 48 gained **108 passes and saved 161 lookups** against that same setting, with zero matched critical losses. At its new lower cost, the strongest affordable measured control was batched GEPA at cap 36, with 406 passes and 3,684 lookups. CPO had one matched critical loss against that setting. The fixed comparison closes the earlier cost gap on the recorded replies. The critical-case gate against every comparison and superiority on fresh replies remain open.

## Reproduce

Use the intact GEPA research and Open Evals archives with pinned GEPA 0.1.4.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_coverage_window
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_coverage_window \
  --execute 7c441680e18c282d5421cf917006adbe2f9699c56beccb2fe12d8b9a9ebce4c5 \
  --out NEW_REPORT.json
```

Two exact-source replays matched byte for byte with sockets and DNS blocked. Both reproduced the published frontier on all three tasks and both precheck modes. Twelve focused tests passed. The CLI rejected a wrong seal and an existing output path. Storage Guard measured 14.4 GiB free. The 18.9 MB temporary source and wheel overlay was removed under the standing LAB exception. [Verification receipt](recorded-coverage-window-verification-v1.json)
