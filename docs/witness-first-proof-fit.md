# Fit first-nominee ranking from independent qualification

The shared-panel backup ceiling found three additional MMLU passes available under the existing trigger and proof. The earlier first-nomination audit found substantially more room among already-paid candidates. This replay fits a ranker for the first nomination using exact qualification outcomes from a different benchmark family. [Backup ceiling](witness-shared-rival-ranking.md) · [First-proof headroom](witness-mmlu-gap.md) · [Runner](../benchmarks/witness_first_proof_fit.py)

The original search still decides when to nominate. The rankers then consider every enrolled candidate with a paid validation grade in that episode. They use the original nominee flag, smoothed accuracy, paid coverage, paired wins and losses against the incumbent, relative case performance, paired margin against the original nominee, and the scheduled tie reserve size. Both fits center features and outcomes inside each episode and give each development episode equal weight.

The promotion ranker fits the exact qualification decision. The primary ranker fits a promoted indicator divided by the reads the proof actually needed. BBH and LMentry labels train both rankers for MMLU. Both MMLU cohorts supply the labels for the reverse fit. No holdout grades enter training or selection. The matched rate control orders candidates by smoothed paid validation accuracy. Every arm submits one candidate to its original independent panel, with the same 24-lookup cap. The primary ranker needs a positive paired lower endpoint against the original first proof and total spend within the seeded control in every cohort.

## Results

| Cohort | Original first proof passes / lookups | Smoothed rate passes / lookups | Fitted promotion passes / lookups | Fitted promotions per lookup passes / lookups |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,095 / 71,087 | 17,211 / 71,255 | 17,215 / 71,233 |
| MMLU prior subjects | 21,180 / 34,122 | 21,180 / 34,122 | 21,180 / 34,122 | 21,180 / 34,122 |
| MMLU additional subjects | 8,976 / 13,639 | 8,976 / 13,639 | 8,976 / 13,639 | 8,976 / 13,639 |

On BBH and LMentry, the primary ranker changed 555 of 1,242 nominees and 421 deployed prompts. It retained 755 promotions and gained 147 held-out passes with 162 additional lookups. Its 71,233 lookups were within the 72,534 seeded total. The paired 95% interval against the original first proof was −0.156 to +0.864 percentage points. Promotion-only fitting gained 143 passes with 184 additional lookups.

Every one of the 539 original MMLU nominations had multiple already-paid candidates. Both fitted rankers and the smoothed rate control retained the original nominee in all 539 episodes and reproduced the original score and cost. The fits used 23,397 candidate qualification labels from BBH and LMentry and 12,546 from MMLU. The primary comparison missed the transfer gate. The trial used archived replies and made zero new provider requests. [Full costs, changed choices, fitted weights, and paired intervals](witness-first-proof-fit-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel in a clean source export. With sockets and DNS disabled, 54 targeted tests passed and two replays produced byte-identical reports. The first-proof control traces, costs, and scores reproduced. A stale seal was rejected, and the prospective live plan reproduced byte for byte. Storage Guard measured 6.2 GiB free. The source export, wheel overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Fit and feature tests](../tests/unit/test_witness_first_proof_fit.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_first_proof_fit
python -B -m benchmarks.witness_first_proof_fit \
  --execute 595d63e25234243e97da44ea9c6b311457156b7a53f46e8031499ab616cf075c \
  --out NEW_REPORT.json
```
