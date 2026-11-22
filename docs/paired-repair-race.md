# Race challengers on a paid repair and a preservation case

Incumbent-first screening cut the cost of paid repair while preserving every decision. This replay tests a different way to find a finalist. It uses the existing validation order to find an incumbent miss and the first incumbent pass. Challengers enter in the existing roster order. A challenger must first pass a case the incumbent missed before it can receive the preservation check. [Previous cost reduction](incumbent-first-paid-repair.md) · [Replay runner](../benchmarks/paired_repair_race.py)

- **Preserve one** seeks one incumbent miss. A challenger qualifies for nomination if it repairs that miss and preserves the incumbent's first observed pass, when one exists.
- **Repair twice or preserve** seeks up to two incumbent misses. It nominates a challenger that repairs a miss and preserves the sampled pass. If the challenger loses that pass, it can still earn nomination by repairing both misses within the cap.

Both races stop at the first challenger with a strict gain on the paid common validation cases. When the incumbent has no pass on the validation panel, one paired repair supplies the gain. Search stays within 19 lookups, and the original separate qualification decides deployment. The replay measures both independent qualification margins across the same eight archived cohorts and prices the races against both CPO controls and the split-safe GEPA budget bounds. [Sealed results](paired-repair-race-results-v1.json)

## MMLU results

Each entry gives held-out passes and paid lookups. The last column gives the split-safe GEPA settings previously selected per subject using the archived holdout. An attainer's score bounds the affordable GEPA ceiling from above when the new budget is below its cost. [Native GEPA comparison](shared-validation-split-safe-transfer.md)

| Cohort and qualification gain | Incumbent-first | Single repair | Preserve one | Repair twice or preserve | Published GEPA attainer |
| --- | ---: | ---: | ---: | ---: | ---: |
| Earlier MMLU, one | 26,646 / 11,435 | 26,635 / 9,061 | 26,637 / 9,876 | 26,653 / 13,371 | 26,655 / 8,574 |
| Disjoint MMLU, one | 56,095 / 10,271 | 56,080 / 9,195 | 56,100 / 9,696 | 56,073 / 12,785 | 56,089 / 6,814 |
| Earlier MMLU, two | 26,633 / 8,624 | 26,633 / 6,841 | 26,630 / 7,461 | 26,632 / 9,551 | 26,655 / 8,574 |
| Disjoint MMLU, two | 56,090 / 7,648 | 56,091 / 6,703 | 56,090 / 7,083 | 56,091 / 8,912 | 56,089 / 6,814 |

The primary two-miss race missed the one-gain gate on both MMLU cohorts. It gained seven passes and cost 1,936 more lookups than incumbent-first on earlier MMLU. On disjoint MMLU it lost 22 passes and added 2,514 lookups. Preserve one gained five passes and saved 575 lookups versus incumbent-first on disjoint MMLU. Its one-gain score was 11 above GEPA, with a paired 95% range of −32 to +54, and it used 2,882 more lookups. The range resamples held-out cases within subjects with the published GEPA settings fixed. At two gains on that cohort it matched incumbent-first's score on 565 fewer lookups. Single repair scored one more pass and used 380 fewer lookups than preserve one at that margin.

On original BBH and LMentry, the two-miss race gained 205 and 181 passes, respectively, over single repair at one qualification gain. The paired 95% ranges were +141 to +273 and +131 to +232. The two-miss race still scored 127 and 307 passes below incumbent-first in those cohorts. Both races remain benchmark-only. Fresh-model quality remains unverified.

## Reproduce offline

Use Python 3.12 with the hash-pinned GEPA 0.1.4 benchmark dependency. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.paired_repair_race
PYTHONHASHSEED=0 python -B -m benchmarks.paired_repair_race \
  --execute 77b1c7830f467406e585ba22cea8bffd1414ecc74804a29518922a5a2591e3ac \
  --out NEW_REPORT.json
```

Two DNS- and socket-blocked source replays produced identical reports at SHA-256 `3f4cfc4f2bc4ff98adabafbbb87ee67f7d7ddb2c0b94c5424b9c6008a599e4ed`. They reproduced all 268 incumbent-first panel-by-margin paths and the published MMLU GEPA scores and costs by subject. Twenty-eight targeted tests passed. A separate exhaustive check matched the first eligible candidate in 8,192 combinations with sufficient budget. Storage Guard measured 2.1 GiB free at preflight. The source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Focused tests](../tests/unit/test_paired_repair_race.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
