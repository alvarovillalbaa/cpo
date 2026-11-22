# Spend the remaining validation cap on a second finalist

The two-sided certificate saved 6,277 lookups without changing the recorded nominees or deployments. This study asks whether to spend the unused per-trial allowance before independent qualification. It keeps the first certified nominee as a fallback and reuses the full paid search prefix. The coverage is eight archived cohorts, 134 model panels, 32 seeded schedules per panel, and two qualification margins. [Two-sided certificate results](two-sided-certificate-cycle.md)

The two strict variants choose a rival using the number of additional favorable replies required for a paired proof. An upgrade must beat the first nominee on the same validation panel and preserve its critical passes. The full reserve requires room for every missing reply in the pair. The minimum reserve admits the shortest possible proof and stops when the remaining allowance cannot certify it. Either variant stops after the first upgrade. Both keep the 19-lookup search cap and use exactly the original qualification path when they retain the first nominee.

After the strict replay, an exploratory repair variant looked for a rival that passes the first already observed nominee miss in validation order. That rival still needs an exact strict gain over the original incumbent and must retain its critical passes. One final nominee enters independent qualification in every variant. [Replay runner](../benchmarks/two_sided_finalist_challenge.py)

## Results

Each entry gives the change from the two-sided cycle in one-gain held-out passes and total paid lookups. [Full results at both margins](two-sided-finalist-challenge-results-v1.json)

| Cohort | Full reserve | Minimum reserve | Complementary repair |
| --- | ---: | ---: | ---: |
| BBH, original | +20 / +1,020 | +20 / +1,194 | −8 / +624 |
| BBH, other checkpoints on previously studied tasks | +16 / +373 | +16 / +453 | +3 / +289 |
| BBH, causal judgment | 0 / +30 | 0 / +43 | 0 / +37 |
| LMentry, original | +35 / +731 | +44 / +956 | +28 / +342 |
| LMentry, other checkpoints on previously studied tasks | +1 / +524 | +18 / +631 | +18 / +304 |
| LMentry, ends-with-word | +26 / +86 | +26 / +116 | 0 / +41 |
| Disjoint MMLU | −4 / +213 | −4 / +237 | −2 / +299 |
| Earlier MMLU | −1 / +291 | −1 / +318 | −10 / +365 |
| **Total** | **+93 / +3,268** | **+119 / +3,948** | **+29 / +2,301** |

At two gains, the variants added 5, 22, and 11 passes and spent 2,762, 3,392, and 1,745 extra lookups, respectively. All three spent more in every cohort at both margins. At one gain, every variant still trailed a published affordable GEPA schedule on the two previously studied BBH cohorts and both MMLU cohorts. The changes remain benchmark-only. [Native GEPA schedules](paired-order-gepa-comparison.md)

## Where continuation can help

At one gain, the two-sided cycle nominated in 1,398 of 4,288 schedules. Among those, 460 had a rival that would independently qualify against the original incumbent and improve the actual held-out deployment. In 299, every such rival tied or lost to the first nominee on validation. In 40, a strict second winner existed but the remaining allowance fell below the minimum certificate cost. The other 121 admitted a strict upgrade in hindsight. This lower-cost proof calculation uses unseen archive grades only to identify eligible rivals after the replay. None of the selection policies uses those grades.

The cycle had no nominee in 2,890 one-gain schedules. The qualification precheck stopped 553. Search failed to nominate despite a better independently qualifying candidate in 254. The other 2,083 had no held-out improvement that met both gates in their supplied roster. On MMLU specifically, 1,485 of 1,856 one-gain schedules reached no first nominee, and only 34 of those contained a better candidate that met both gates. Post-nomination lookahead cannot reach the no-nominee cases. The MMLU results bound the room for improving selection within this fixed roster and gate. Fresh-model superiority remains unverified.

## Reproduce offline

Use the pinned GEPA 0.1.4 wheel and a fresh output path. The two socket-blocked source replays matched byte for byte at SHA-256 `609b7e30bd65b4204ed82866e5fffbdc99e1010333929c2ed6b3fbffda0e538c`. They reproduced all 268 baseline panel-by-margin traces, checked both exact gates, and reconciled the validation cap against the actual ledger. Twelve targeted tests passed. Storage Guard measured 2.0 GiB free. The scratch export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Tests](../tests/unit/test_two_sided_finalist_challenge.py) · [Benchmark dependency](../requirements-benchmark.txt) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.two_sided_finalist_challenge \
  --execute 96ada858c2ed6646cb23e4128d9ad7a4b51272b05b53223fa0178acffb60f43d \
  --out NEW_REPORT.json
```
