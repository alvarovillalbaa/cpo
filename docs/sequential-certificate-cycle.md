# Certify a challenger as soon as its probe passes

`run_sequential_certificate_cycle` is an opt-in alternative to buying all reserved shared probes before attempting a validation certificate. It retains the incumbent qualification precheck, the fixed validation cap and the separate qualification panel. [Public API](../cpo/sequential_certificate_cycle.py) · [Original cycle](prechecked-certificate-cycle.md)

```python
from cpo.sequential_certificate_cycle import run_sequential_certificate_cycle

result = run_sequential_certificate_cycle(
    incumbent,
    candidates,
    validation_rows,
    qualification_rows,
    evaluate,
    metric_limit=13,
    qualify=qualify,
    minimum_gain=1,
)
```

Probe challengers in roster order on the first case the incumbent missed. If the probe passes, use the remaining validation budget to try to certify that challenger immediately. The certificate still needs more paid passes than the incumbent and preserves its protected passes. If the proof fails, try the next challenger whose best possible certificate fits. If no passing probe produced a certificate, the screen can finish an affordable certificate for an earlier probe failure. Only the first certified nominee can reach independent qualification. [Validation and qualification callbacks](prechecked-certificate-cycle.md)

## Archived results

The replay keeps the published starts, fixed challenger rosters, cap 13, case splits, and one- or two-gain qualification thresholds. It reproduces the paid paths of both published CPO controls across 102 panels and 32 schedules each. Each comparison below pairs the new screen with the published CPO screen at the same qualification margin. [Paid-path fingerprints and full results](sequential-certificate-cycle-results-v1.json)

| Cohort | Qualification gains | Held-out passes / lookups | Pass change and paired 95% range | Lookups saved |
| --- | ---: | ---: | ---: | ---: |
| BBH | 1 | 9,297 / 12,127 | −66 [−113, −16] | 440 |
| BBH | 2 | 8,914 / 11,797 | −39 [−66, −11] | 310 |
| LMentry | 1 | 5,346 / 7,101 | +180 [117, 244] | 4 |
| LMentry | 2 | 4,980 / 6,913 | +154 [106, 202] | −2 |
| Disjoint MMLU | 1 | 56,101 / 9,245 | +22 [3, 42] | 351 |
| Disjoint MMLU | 2 | 56,094 / 6,934 | 0 [0, 0] | 176 |
| Earlier MMLU | 1 | 26,627 / 9,640 | +14 [−4, 33] | 613 |
| Earlier MMLU | 2 | 26,628 / 7,451 | 0 [−6, 5] | 295 |

One-gain CPO on LMentry scored **83 passes above GEPA’s archived subject-tuned hindsight ceiling** at 7,101 lookups. The earlier exact GEPA budget sweep found a maximum of 5,263 passes at the larger 7,105-lookup budget, attained by a schedule using only 7,100 lookups. Those budgets bound the current result from both directions and make the ceiling exact at 7,101. On disjoint MMLU the analogous ceiling was 56,113, 12 passes above one-gain CPO at its new budget. [GEPA modes, wrappers, and attaining subject schedules](threshold-precheck-gepa-frontier.md)

The BBH losses occurred at both qualification margins. This API stays opt-in. The LMentry ceiling comparison is an observed margin over settings selected with held-out grades. The paired ranges in the table compare the two CPO screens. This fixed-roster archive leaves fresh-model performance and generalization to new candidate pools unverified.

Immediate certification improved the pooled BBH and LMentry results on previously studied tasks with two other archived checkpoints. The paid budget rule did not consistently choose between the original and immediate screens. [Budget routing and checkpoint transfer](certificate-budget-route.md)

## Reproduce

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_sequential_certificate_screen
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_sequential_certificate_screen \
  --execute dafb9cc71d47337fcdcaf584fba5bbf43f9bd8c215f46206826aee0ab2cc881a \
  --out NEW_REPORT.json
```

The public cycle reproduced the prototype’s paid callback order, budgets and grades on all 6,528 candidate paths. The clean source and independently installed wheel produced byte-identical reports at SHA-256 `9ff2aa90229bdcbe805de1a75644c18161641a572f16e198ce30cbbd9be6df9b`. Both runs blocked DNS and outbound sockets. The wheel replay placed the benchmark and sealed inputs beside the installed package. The source suite passed 24 tests and the wheel passed the four new API tests. The CLI rejected the prototype seal before writing a result. Storage Guard measured 2.9 GiB free. The temporary export, wheel and publication checkout fit the standing 0.2 GiB LAB exception. [Replay driver](../benchmarks/recorded_sequential_certificate_screen.py) · [API tests](../tests/test_sequential_certificate_cycle.py)
