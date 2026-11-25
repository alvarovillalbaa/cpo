# Extend narrow uniform validation when the short race stalls

The four-case cap saved lookups and gave up some of uncapped routing's LMentry gains. This replay tests two conditions for reopening the original funded panel. It keeps the two-challenger rosters, case order, opening route, schedule feedback, and independent qualification. Only noncritical uniform validations with more than four funded cases enter the new screen. [Fixed-depth results](validation-routed-depth.md) · [Runner](../benchmarks/validation_routed_tail.py) · [Sealed results](validation-routed-tail-v1.json)

Both variants run the exact ordered uniform race on the first four cases. **Stalled tail** extends after that race retains the incumbent. It reads the incumbent on the remaining cases until the best possible challenger score can no longer win or a full race is needed. Even an unread challenger reply can contribute a pass in that upper bound. **Close tail** also extends when a four-case nominee leads the incumbent by one pass. The expanded race uses the full originally funded case set and reuses every previously read grade. It passes only its chosen nominee to the independent qualification gate. [Focused tests](../tests/unit/test_validation_routed_tail.py)

Each cell shows held-out passes and paid lookups. The language mix contains 2,048 recorded BBH, LMentry, and MMLU episodes with some reused cases. Promptolution contains 64 episodes. The benchmark reproduced the fixed-depth arms and all original baselines on the same splits.

| Suite | Settled CPO | Uncapped routed | Four-case cap | Stalled tail | Close tail |
| --- | ---: | ---: | ---: | ---: | ---: |
| Language mix | 52,396 / 71,741 | 52,566 / 78,817 | 52,482 / 60,623 | 52,593 / 73,313 | 52,551 / 77,357 |
| Bounded LMentry | 5,576 / 14,007 | 5,690 / 17,049 | 5,611 / 12,867 | 5,677 / 15,538 | 5,677 / 16,407 |
| Tie LMentry | 899 / 5,045 | 929 / 6,676 | 885 / 4,882 | 925 / 6,151 | 928 / 6,557 |
| Promptolution GSM8K | 2,472 / 906 | 2,440 / 850 | 2,404 / 728 | 2,436 / 768 | 2,438 / 812 |
| Promptolution SST5 | 1,452 / 1,549 | 1,439 / 1,598 | 1,434 / 1,229 | 1,441 / 1,336 | 1,445 / 1,473 |
| Promptolution total | 3,924 / 2,455 | 3,879 / 2,448 | 3,838 / 1,957 | 3,877 / 2,104 | 3,883 / 2,285 |

Stalled tail gained 27 passes and saved 5,504 lookups over uncapped routing on the language mix. It recovered 106 of the 123 LMentry passes the four-case cap lost. Against settled CPO, it gained 197 passes at a cost of 1,572 additional lookups. The LMentry paired 95% case ranges against settled CPO were +57 to +146 and +7 to +45 passes. Both LMentry ranges against uncapped routing included zero. The receipt records the paired ranges per cohort and reselects the strongest affordable GEPA and halving settings in each bootstrap draw.

On Promptolution, stalled tail saved 344 lookups and lost two passes against uncapped routing. The paired 95% range was −0.24 to +0.17 percentage points. Settled CPO had 47 more passes for 351 more lookups. Stalled tail beat the strongest affordable halving setting by 57 passes and the strongest affordable native GEPA setting by 360 passes, with 93 and 83 additional lookups respectively. The matched ranges were +0.24 to +1.68 and +4.43 to +8.07 percentage points.

Extending one-pass nominees bought 4,044 extra lookups on the language mix and gave up 42 passes compared with extending only after a stall. It gained six passes with 181 more lookups on Promptolution. Stalled tail is the stronger candidate from this replay for reducing the cost of uncapped routing. Both policies are benchmark variants. Fresh-model performance remains unverified.

## Reproduce offline

Use Python 3.12, the pinned GEPA 0.1.4 wheel, and the original Promptolution corpus. Running the command without arguments previews the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.validation_routed_tail \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 0ab86333ec3131f9af910531b7e617ca828933fb19a34c008efa9bc8acd5a05d \
  --out NEW_REPORT.json
```

Two socket-blocked replays produced byte-identical receipts with SHA-256 `2c426656fc00e48138f99ef40fa1518e4149aa0e7e8f32e0051c03296df3c613`. All 42 focused tests passed, including 256 generated five- and six-case panels that checked nomination, exact score reuse, and lookup accounting. The CLI rejected a stale seal and an existing output path. The replay sent zero provider requests. Storage Guard measured 9.0 GiB free. The isolated source export, wheel overlay, and publication worktree used 123 MiB within the standing LAB storage exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
