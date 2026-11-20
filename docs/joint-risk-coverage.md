# Test critical-case coverage during joint sampling

At cap 72, the original TPE and CPO hybrid lost four critical observations against sequential GEPA and two against batched GEPA. All six involved short outages with missing evidence. That condition appeared in full validation and independent qualification. The three-case sampling prefix contained two posted long outages and one ordinary case. [Original matched outcomes](joint-sampler-comparison.md)

## Protocol

The replay keeps the original fixed instruction and demonstration pool, search caps of 48 and 72, independent qualification, and held-out cases. It repeats the six original fixture seeds and then uses six other seeds from the same policy generator. Risk groups use input facts. Outages use evidence status and the 120-minute boundary. Tickets use the topic. Warehouses use inspection status and release tier.

- **Diverse prefix** keeps the three-case budget and original critical quota. It favors distinct, less-represented critical groups and keeps the original ordinary cases in place. The same full validation cases remain available.
- **Coverage gate** requires every represented critical group to have at least one pass in the nominee's fully scored validation evidence.
- **Combined** uses the diverse prefix and coverage gate.
- **Fallback variants** keep the strongest exact candidate the coverage rule would otherwise reject. They use it only when the sampler produces no coverage-qualified nominee. The fallback receives the original independent qualification check.

The original hybrid and both official GEPA modes run on the same case cohorts as controls. No held-out outcomes guide search or promotion. [Runner](../benchmarks/joint_risk_coverage.py)

## Results

Each cell reports cap-72 holdout passes out of 324 / paid lookups.

| Method | Original seeds | Additional seeds |
| --- | ---: | ---: |
| Original hybrid | 311 / 1,064 | 306 / 1,163 |
| Diverse prefix | 311 / 1,045 | 302 / 1,141 |
| Coverage gate | 234 / 1,020 | 216 / 1,090 |
| Combined | 234 / 1,023 | 216 / 1,077 |
| Coverage gate with fallback | 311 / 1,095 | 306 / 1,181 |
| Combined with fallback | 311 / 1,098 | 302 / 1,168 |
| Batched GEPA | 302 / 1,022 | 306 / 1,035 |
| Sequential GEPA | 300 / 1,022 | 298 / 1,118 |

Diversifying the prefix saved 19 lookups at the same score on the original cap-72 seeds and kept all six matched critical losses. On the additional seeds it saved 22 lookups, lost four passes, and produced 12 matched critical losses against batched GEPA and ten against sequential GEPA. The original hybrid had two and zero respectively.

On the additional cap-72 seeds, the combined rule kept the starting prompt on all six outage panels. The fallback restored those six promotions and all 90 lost passes. Across both caps and seed cohorts, the combined rule with fallback restored **22 outage promotions**. A separate exhaustive check examined the fully scored validation grid after those replays. All 22 restored panels had **zero** candidates that could strictly improve on the incumbent, preserve its critical passes, and pass at least one case in every critical group. This diagnostic used no holdout outcomes and supplied no evidence to the sampler. [Full results and candidate-availability audit](joint-risk-coverage-results-v1.json)

The coverage-only fallback chose the same final programs as the original hybrid in all 72 panels. It recovered accuracy by allowing the verified alternatives that had failed the coverage rule. Its matched critical losses also matched the original hybrid. The fixed fixture pool lacked the combinations needed to make the harder validation rule useful. Fresh proposal generation and live critical-case performance remain unverified.

## Reproduce

Use the pinned GEPA 0.1.4 and Optuna 4.5.0 wheels in an isolated environment. The [wheel receipt](joint-risk-coverage-verification-v1.json) records the verified fingerprints. The [sampler environment](joint-sampler-verification-v1.json) records the shared dependency versions.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.joint_risk_coverage
PYTHONHASHSEED=0 python -B -m benchmarks.joint_risk_coverage \
  --execute c623f5416625f5e4a173f9e47686205e8c0c769a7413877b38268f247b631de6 \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked and reproduced 108 published control traces. Eight focused tests passed. The CLI rejected a wrong seal and an existing output path. Storage Guard measured 20.2 GiB free. The 28.2 MB temporary source and wheel overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_joint_risk_coverage.py)
