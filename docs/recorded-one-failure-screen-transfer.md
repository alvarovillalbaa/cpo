# Transfer a validation reserve that allows one failed reply

The first-miss screen can probe more challengers by reserving only the minimum number of favorable replies needed for a certificate. The preceding comparison showed a large drop in nominations when that minimum was used. This replay reserves space for one failed reply, capped at the cost of the complete finalist panel. It keeps the same first-miss probe, roster order, exact validation gain, and independent qualification. All three screen policies use cap 13. [Earlier comparison](recorded-early-certificate-screen.md) · [Transfer runner](../benchmarks/recorded_one_failure_screen_transfer.py)

The transfer uses 30 archived panels across 15 MMLU subjects and five model checkpoints outside both the cap-discovery and prior screen cohorts. It takes all eligible aligned subject pairs from three pinned correctness snapshots. The 960 seeded trials cover 1,418 distinct held-out cases. The source snapshots were previously used for other research. [Low-budget archive](low-budget-transfer.md) · [Late-miss archive](late-miss-transfer.md) · [Posterior transfer archive](posterior-model-transfer.md)

The gate requires a positive observed advantage and a nonnegative lower paired bound against the best affordable fixed CPO or GEPA setting, including retained starts. It sweeps fixed CPO caps 6 through 54 and both native GEPA modes at caps 6 through 180. Both methods pay for search and qualification. Each paired case draw keeps the two model scores and all seed results together and reselects the strongest affordable control.

| Screen reserve | Nominees / promotions | Passes / paid lookups | Best affordable control | Margin and paired 95% range |
| --- | ---: | ---: | --- | ---: |
| Minimum | 23 / 4 | 56,070 / 8,987 | Retain starts, 56,065 at zero lookups | +5, −19 to +14 |
| One failed reply | 55 / 8 | 56,056 / 9,274 | Retain starts, 56,065 at zero lookups | −9, −33 to +2 |
| Complete panel | 103 / 19 | 56,079 / 9,596 | Sequential GEPA cap 16, 56,068 at 9,320 lookups | +11, −26 to +32 |

The one-failure reserve missed the gate. It changed four deployments relative to the minimum reserve and lost 14 passes overall while spending 287 more lookups. The complete-panel reserve had the highest observed CPO score at cap 13, with an inconclusive paired range against the strongest affordable control. The original unscreened cap-13 race scored 56,063 at 9,010 lookups. These comparisons concern selection among archived prompts. Fresh-model performance remains unverified. [Full results and panel traces](recorded-one-failure-screen-transfer-results-v1.json)

A follow-up measured how much improvement remained after the strict gates and the paid probes. [Coverage and funding ceilings](recorded-screen-coverage-ceiling.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_one_failure_screen_transfer
python -B -m benchmarks.recorded_one_failure_screen_transfer \
  --execute 3d9c5c69d9568293087dbd3b794d15fc95a5fa7767fc92ab09e1403653c8f234 \
  --out NEW_REPORT.json
```

Two clean-export replays with DNS and sockets blocked matched byte for byte at SHA-256 `e4f2ac401077b83705fa79befa036af71d00fb65e66b1ae625af9900f42b288d`. All 36 targeted tests passed. Direct replay checked all 2,880 screening paths and the three reported control points. The CLI rejected the predecessor seal. Storage Guard measured 3.1 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Regression tests](../tests/unit/test_recorded_one_failure_screen_transfer.py)
