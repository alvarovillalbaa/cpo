# Defer reserved probes in the certificate screen

`run_deferred_certificate_cycle` keeps the same roster prefix, certificate allowance, and independent qualification as the reserved screen. It buys the next shared probe only when the outcome could affect selection. [Public API](../cpo/deferred_certificate_cycle.py) · [Reserved screen](prechecked-certificate-cycle.md)

```python
from cpo.deferred_certificate_cycle import run_deferred_certificate_cycle

result = run_deferred_certificate_cycle(
    incumbent,
    candidates,
    validation_rows,
    qualification_rows,
    evaluate,
    metric_limit=19,
    qualify=qualify,
    minimum_gain=1,
)
```

The algorithm reserves every probe that the eager screen would buy before it computes how many validation reads can fund a certificate. Passing probes receive the same roster priority, and failed probes enter the same fallback order. If the incumbent passed `p` cases, a successful probe leaves at least `p` fresh passes to prove a gain. The screen can stop buying probes when fewer than `p` certificate reads remain. When the cap admits no challenger, it can skip the incumbent validation panel too. The qualification panel still uses the original precheck and exact proof. [Callback contract](prechecked-certificate-cycle.md)

For a stable grade per prompt and case, the two schedules select the same nominee and deployment. Actual callback order can differ. `result.search.evaluations` counts the callbacks the deferred cycle bought. The original roster and certificate allowance still use the full reservation.

## Recorded lookup savings

The archive covers 134 model panels, each with 32 schedules, at one and two qualification gains. Six validation cases and eight challengers make cap 19 the first cap that admits the complete roster while reserving the finalist suffix. At each cap the replay preserves every nominee, deployment, qualification receipt, and non-probe callback. [Paid paths and cohort results](deferred-certificate-cycle-results-v1.json)

| Validation cap | Eager lookups | Deferred lookups | Lookups saved | Paths with savings |
| --- | ---: | ---: | ---: | ---: |
| 13 | 99,855 | 99,002 | 853 (0.85%) | 853 of 8,576 |
| 19 | 141,060 | 127,590 | 13,470 (9.55%) | 2,589 of 8,576 |

Every omitted callback at these caps was a challenger’s shared probe. The remaining callback sequence also matched the eager sequence after removing the omitted probes. At cap 13 the lower spend left the set of affordable fixed GEPA settings unchanged for every cohort and margin, so the earlier paired comparisons still apply.

## Full-roster comparison with GEPA

The replay compares cap-19 CPO with both native GEPA modes and all three published qualification wrappers at CPO’s actual lookup budget. Each paired draw reselects the highest-scoring affordable fixed control or retained starts. The table gives pass differences and paired 95% ranges. The gate requires a positive observed difference and a nonnegative lower endpoint. [Full comparison receipt](deferred-certificate-gepa-frontier-results-v1.json)

| Cohort | One-gain CPO passes / lookups | One-gain margin | Two-gain CPO passes / lookups | Two-gain margin |
| --- | ---: | ---: | ---: | ---: |
| BBH, original | 9,548 / 16,146 | +345 [269, 425] | 8,998 / 15,149 | −187 [−242, −132] |
| BBH, other checkpoints on previously studied tasks | 4,843 / 9,098 | +168 [122, 212] | 4,790 / 8,439 | +115 [76, 155] |
| BBH, causal judgment | 591 / 1,123 | +1 [−10, 12] | 569 / 1,016 | −21 [−31, −12] |
| LMentry, original | 5,650 / 8,781 | +650 [572, 729] | 5,192 / 8,386 | +493 [426, 560] |
| LMentry, other checkpoints on previously studied tasks | 5,307 / 6,174 | +504 [440, 569] | 4,963 / 5,402 | +325 [273, 372] |
| LMentry, ends-with-word | 263 / 1,170 | +30 [18, 43] | 256 / 1,186 | +23 [15, 30] |
| Disjoint MMLU | 56,094 / 12,933 | +23 [−16, 56] | 56,094 / 9,017 | +29 [10, 46] |
| Earlier MMLU | 26,619 / 13,739 | −9 [−40, 19] | 26,630 / 9,831 | +5 [−4, 11] |

Ten of sixteen comparisons passed. Retaining starts was the strongest affordable control for both two-gain MMLU comparisons. The cap-19 analysis compares one setting pooled across each cohort. It leaves per-subject hindsight and fresh-model performance unverified.

## Reproduce lookup savings

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_deferred_certificate_cycle
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_deferred_certificate_cycle \
  --execute 36ec3fa066638c955bd0d2566ccb9e8cc74f13b4db811734cb83cd4a6caeb4d3 \
  --out NEW_CYCLE_REPORT.json
```

The clean source and installed wheel matched byte for byte at SHA-256 `2bf7107a2e761aa55c4c9d5055aaade0012e3e3bf956317f63c8396d5963369f` with DNS and outbound sockets blocked. The replay checked 17,152 paired paths. The tests also checked 57,344 small validation boards and cap combinations, including critical cases and caps with no funded challenger. All 25 targeted source tests and three installed API tests passed. The CLI rejected the predecessor seal before creating a report. [Cycle replay](../benchmarks/recorded_deferred_certificate_cycle.py) · [API tests](../tests/test_deferred_certificate_cycle.py)

## Reproduce the full-roster GEPA comparison

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. The runner replays every fixed GEPA setting whose previously sealed cost fits either cap-19 CPO budget. It reproduces those costs and grades, verifies the CPO callback hashes, and reselects the strongest affordable common setting or retained starts on each paired draw. [Pinned wheel](../requirements-benchmark.txt) · [Replay driver](../benchmarks/recorded_deferred_certificate_gepa_frontier.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_deferred_certificate_gepa_frontier
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_deferred_certificate_gepa_frontier \
  --execute 4cbd3748ee07bc159b33418627aef06145712bd82e1970acddf423b0c9b1b7d9 \
  --out NEW_GEPA_REPORT.json
```

The two clean-source runs matched byte for byte at SHA-256 `c8dd4548189087fdecbfc8a7b43edc647e8361e19cf7fcfb9a5bea02652b4e05`. They reproduced all 1,113 affordable cohort-setting totals. Another 7,936 direct executions of selected settings verified the matched controls. DNS and outbound sockets were blocked, and the CLI rejected the cycle report’s seal before writing a GEPA report. Storage Guard measured 3.1 GiB free. The temporary export, wheel and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.
