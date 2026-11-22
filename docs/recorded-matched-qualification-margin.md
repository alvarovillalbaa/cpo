# Give GEPA the same stronger qualification rule

The two-gain qualification rule improved the original CPO screen in both archived MMLU cohorts. This replay applies the same rule to sequential and batched GEPA and retains the original one-gain versions as controls. Both qualification rules reuse the paid incumbent prefix, order the remaining replies by expected proof cost, and keep the original independent cases. The replay verifies that changing the qualification rule keeps the native search boundaries, lookup counts, and nominees. [CPO qualification experiment](recorded-qualification-margin.md) · [Replay runner](../benchmarks/recorded_matched_qualification_margin.py)

The comparison sweeps all integer GEPA search caps from 6 to 180 under each rule. Each paired draw reselects the highest-scoring affordable common setting, including retaining starts, at CPO’s realized search-plus-qualification cost. The gate requires a positive observed margin with a nonnegative lower paired bound. The original one-gain comparisons and CPO decisions reproduce before the new comparisons are reported.

| Archived cohort | Two-gain CPO passes / lookups | Best affordable fixed GEPA or retained starts | CPO margin and paired 95% range | GEPA subject-specific hindsight |
| --- | ---: | --- | ---: | ---: |
| Earlier screen, 896 trials | 26,628 / 10,001 | Retain starts, 26,625 / 0 | +3, −7 to +9 | 26,653 / 9,048 |
| Disjoint transfer, 960 trials | 56,094 / 9,395 | Sequential cap 16 with one-gain qualification, 56,068 / 9,320 | +26, 0 to +44 | 56,111 / 8,368 |

CPO cleared the fixed-setting GEPA gate on the transfer cohort when GEPA could use either qualification rule. With both methods requiring two gains, the strongest affordable GEPA control on the transfer cohort was retaining the starts. CPO led that fixed comparison by 29 passes, with a paired range of +10 to +46. The earlier cohort remained inconclusive.

A separate hindsight calculation lets GEPA choose the search mode, cap, and qualification rule per subject, shared by its two model panels. It leads CPO on both cohorts within the same total lookup budgets. Its settings use the held-out grades. The prior transfer comparison against the broader CPO control set also remains inconclusive. Fresh-model performance remains unverified. [All measured settings, paired ranges and attaining subject schedules](recorded-matched-qualification-margin-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_matched_qualification_margin
python -B -m benchmarks.recorded_matched_qualification_margin \
  --execute 4f403d89053e8baef92d69dfa13b5def1de4edd530a514300d1aa65193c3ff82 \
  --out NEW_REPORT.json
```

Two clean-export runs with DNS and sockets blocked matched byte for byte at SHA-256 `6841281aef1b1ef533e6c9f424e681aa3fce33dbfcad35943af33ca0292f6cfd`. The replay checked 25,056 native search paths under both qualification rules. Direct runs verified all selected common and subject-specific controls across 110 setting and panel combinations. All 43 targeted tests passed. The CLI rejected the predecessor seal. Storage Guard measured 3.0 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Regression tests](../tests/unit/test_recorded_matched_qualification_margin.py)
