# Retry training after a remaining validation miss

The [shared qualification comparison](opening-family-qualification.md) stopped on one shifted panel after four passing training probes, although a paid validation check had found an unresolved miss. `run_validation_guided_repair_cycle` now accepts `retry_probe_limit`. A positive limit lets the cycle try less-exposed training rows after a later routed batch passes. The allowance is shared across later stages, and the probes stop at the first observed failure. Search still reserves a complete validation panel before any new probe and still sends only training observations to the proposer. The default is zero. [API](../cpo/validation_guided_repair.py)

The pilot selected a limit of eight. It used six extra probes on the earlier failing panel, recovered both critical cases, and finished one call below batched GEPA. The confirmation froze that cap and tested 36 disjoint scripted panels with original and shifted faults. Both GEPA controls used the same adaptive qualification scheduler as CPO. Each cell gives exact holdout passes out of 648 and total counted calls.

| Method | Original faults | Shifted faults |
| --- | ---: | ---: |
| Validation-guided CPO | 644 / 2,275 | 644 / 2,313 |
| CPO with retry | 648 / 2,286 | 648 / 2,324 |
| Sequential GEPA | 570 / 2,524 | 563 / 2,499 |
| Batched GEPA | 522 / 2,282 | 512 / 2,283 |

The retry preserved every baseline pass and every matched critical pass against both GEPA arms. It gained four passes over CPO without retries in each mode and cleared both sequential GEPA gates. It triggered on two panels in each mode and found a usable training failure every time. The retry used four more calls than batched GEPA with original faults and 41 more with shifted faults, so the full confirmation gate failed on cost. [Sealed results](opening-residual-retry-results-v1.json)

A follow-up swept nine GEPA search ceilings on these same input panels. At CPO’s realized cost, CPO led the best per-panel GEPA hindsight allocation by 75 passes with original faults and 76 with shifted faults. [Matched-cost comparison](opening-retry-cost-frontier.md)

A second replay used exact bounds to reduce the last draft's validation reads. It preserved all decisions and closed the fixture call-count gap with batched GEPA. [Terminal validation certificate](opening-validation-certificate.md)

## Reproduce offline

Use GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_residual_retry
PYTHONHASHSEED=0 python -B -m benchmarks.opening_residual_retry \
  --execute 2b312cbb2df33c662179c0fe5afbfb89899f99e77e650558900f4f8e9ed42750 \
  --out NEW_REPORT.json
```

Two clean source replays and one installed-wheel replay matched byte for byte. Each reproduced the baseline’s exact prior traces and exercised 72 input panels under two fault modes. All 24 focused tests passed in each environment, including a check that the retry leaves enough budget for complete validation. The runner refused a wrong seal and preserved an existing file. Storage Guard measured 4.6 GiB free and all scratch exports were removed under the standing LAB exception. Live qualification remains pending. [Verification receipt](opening-residual-retry-verification-v1.json)
