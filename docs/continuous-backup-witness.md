# Choose the case for a terminal backup probe

The terminal backup benchmark buys at most one new validation grade at an observed incumbent miss. Its original rule chooses the first such case in the paid ledger that the challenger has yet to answer. This experiment freezes the nominee rejection, backup candidates, single-probe limit, qualification proof and budget. It varies which eligible case receives that probe. [Original backup benchmark](continuous-archive-backup.md) · [Replay runner](../benchmarks/continuous_backup_witness.py)

- **Last miss** selects the last eligible case in the paid ledger.
- **Paid peers** prefers the highest smoothed pass rate among other challengers on an eligible case. It uses only validation grades bought in the same episode.
- **Finalist miss** prefers a case the rejected finalist was observed to fail, using paid peer rates to break ties.
- **Adjusted peers** chooses by the paid peer rate and updates the original repair probability with the paid count on that case. The original prediction carries the weight of four prior observations.

Paid repairs retain their original priority. Only adjusted peers changes the global ranking of opportunities before each budgeted replay. In the other arms, the offered row changes and any resulting difference in cost can change how many subsequent attempts fit.

The diagnostic also gives hindsight every eligible witness while retaining one probe per candidate, the original qualification condition and the same cohort allowance. It uses recorded outcomes and the minimum proof price. It compares this relaxed upper bound with the corresponding bound for the original first-miss rule. No target outcome is visible to the actual scheduler before it pays for the grade.

A second diagnostic replays profitable options through the exact proof to price their actual charges. Its upper bound allows any allocation whose settled charges fit. Its lower bound also reserves the largest difference between a start quote and settled charge. A selected schedule whose total charge plus that margin fits can start every attempt within the allowance in any order. Both bounds use hindsight to select candidates and retain one backup per episode.

## Results

All four alternatives preserved every deployment across 2,048 episodes. Each finished at 53,486 held-out passes and used 562 backup lookups across the seven cohorts. The adjusted policy changed some cohort prices by one lookup and increased passed probes from 31 of 166 to 35 of 171. The number of promotions following a new probe remained six.

| Cohort | Episodes with alternative witness | First miss, settled-cost bounds | Any eligible witness, settled-cost bounds |
| --- | ---: | ---: | ---: |
| [Bounded BBH](continuous-backup-witness-bounded-bbh-v1.json) | 28 | +57 to +58 | +63 |
| [Bounded LMentry](continuous-backup-witness-bounded-lmentry-v1.json) | 31 | +93 to +95 | +99 to +100 |
| [Bounded MMLU](continuous-backup-witness-bounded-mmlu-v1.json) | 3 | 0 | 0 |
| [Four-case MMLU](continuous-backup-witness-four-case-mmlu-v1.json) | 22 | +2 | +4 |
| [Tie BBH](continuous-backup-witness-tie-bbh-v1.json) | 56 | +18 | +18 |
| [Tie LMentry](continuous-backup-witness-tie-lmentry-v1.json) | 43 | +16 | +16 |
| [Additional MMLU](continuous-backup-witness-additional-mmlu-v1.json) | 13 | +8 | +8 |
| Total | 196 | +194 to +197 | +208 to +209 |

The bounds give possible hindsight gains over joint qualification without backups. The actual one-probe policy gained 54 passes. The first-miss rule alone supported a schedule with at least another 140 passes at the same budgets when outcomes were known. Allowing any witness raised the relaxed minimum-price upper bound from 209 to 222 and the settled-charge upper bound from 197 to 209. Most of the remaining hindsight headroom was already in the original witness menu, particularly on bounded BBH and bounded LMentry. The replays establish archive behavior with known candidate grades. Live improvement remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Preview a different cohort's seal by omitting `--execute` and `--out`. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_backup_witness \
  --cohort bounded-BBH \
  --execute f8a023ee9431c11acffccad220026e67a4dd65cd01958310e60dcdd8fca3c69e \
  --out NEW_REPORT.json
```

Fifteen targeted tests passed. Two CLI replays per cohort matched byte for byte with DNS and outbound sockets blocked. Independent enumeration of 200 small budgets and all their dispatch orders confirmed that each exact optimum lay within the two settled-cost bounds. Storage Guard measured 10.0 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_continuous_backup_witness.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
