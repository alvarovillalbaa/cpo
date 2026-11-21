# Fit the training check on other benchmarks

On the original math replay, requiring a training gain helped AIME and hurt ARC-AGI. This study tests whether a rule fit on BBH, LMentry, and MMLU can tell when to require that check. CPO keeps the original strict validation nominee and exact independent qualification. After qualification passes, the rule sees only two facts about the already-paid validation grades. It knows whether the nominee gained one pass or several, and whether it lost any incumbent pass. The rule cannot change which nominee qualifies or which qualification replies are bought. [Original training waiver study](recorded-margin-corroboration.md) · [Runner](../benchmarks/recorded_calibrated_training_route.py)

Replay both training policies on the 26 archived donor panels using their original case schedules. Enroll a validation pattern only if it has at least eight qualified trials in each donor family and the equally weighted mean of their held-out accuracy changes from the training check is positive. Freeze the result before replaying AIME and ARC-AGI. Neither math archive supplies fit labels. No pattern met both conditions. The one-pass gain with zero lost validation passes was the only pattern with enough support, and requiring training lowered its donor score in all three families. [Donor archive and splits](recorded-first-certificate-transfer.md)

| Validation evidence | BBH qualified trials / pass change | LMentry qualified trials / pass change | MMLU qualified trials / pass change |
| --- | ---: | ---: | ---: |
| One gained pass, zero lost | 27 / −24 | 8 / −9 | 25 / −3 |
| One net gain, at least one lost | 8 / −5 | 2 / +6 | 1 / 0 |
| Multiple gained passes, zero lost | 18 / −35 | 35 / −32 | 4 / −5 |
| Multiple net gains, at least one lost | 7 / −9 | 2 / −4 | 0 / — |

## Frozen rule on the math archives

The fitted rule always skipped training. The controls use the same nominee, qualification precheck, and expected-cost certificate. The always-training control uses the previous exact, price-aware training proof. Cells report held-out passes and paid lookups. The replay reproduced both fixed policies' earlier scores and the original GEPA frontier. [Sealed report](recorded-calibrated-training-route-results-v1.json)

| Archive and roster | Fitted rule | Always require training |
| --- | ---: | ---: |
| AIME, original, four challengers | 486 / 1,040 | 489 / 1,117 |
| AIME, original, eight challengers | 476 / 1,438 | 485 / 1,530 |
| AIME, rotated, four challengers | 4,036 / 7,643 | 4,069 / 8,117 |
| AIME, rotated, eight challengers | 4,002 / 10,908 | 4,062 / 11,487 |
| ARC-AGI, original, four challengers | 1,561 / 1,302 | 1,561 / 1,844 |
| ARC-AGI, original, eight challengers | 1,578 / 1,502 | 1,578 / 2,041 |
| ARC-AGI, rotated, four challengers | 13,878 / 7,007 | 13,757 / 8,226 |
| ARC-AGI, rotated, eight challengers | 13,932 / 8,239 | 13,818 / 9,611 |

On eight-challenger rotated ARC-AGI, the fitted rule gained 197 passes over the best affordable GEPA at the lookup budget, with a paired case-resampled 95% range of +79 to +318. At historical evaluator prices it gained 164, with a range of +58 to +273. The four-challenger rotation gained 154, with a range of +65 to +245 under both budgets. On eight-challenger rotated AIME, the fitted rule lost 78 passes to the best affordable GEPA with a range of −142 to −39. The original AIME start scored 500 with zero lookups. Both affordable ARC root ranges crossed zero. These are reused fixed-pool archives. The rule failed to transfer across the two math benchmarks and stays out of the default policy.

The effects differed even within the same validation pattern. At eight challengers, requiring training on multiple gains with zero lost validation passes added 43 held-out passes on rotated AIME and lost 62 on rotated ARC-AGI. For one gain with zero validation losses, requiring training added 15 on AIME and lost 52 on ARC-AGI. The two validation cues alone could not distinguish the cases where corroboration helped.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two full runs matched byte for byte with network sockets and DNS blocked. All 43 targeted tests passed from a clean source export, including family weighting, support requirements, and the independent qualification boundary. The stale seal was rejected, and the public selector parity receipt and sealed live-plan preview reproduced exactly. Storage Guard measured 2.9 GiB free. The source export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_calibrated_training_route
python -B -m benchmarks.recorded_calibrated_training_route \
  --execute 22f5ac4ca9e4a84596b4f6626b5de1e50fa6b281c152d9205811d2e2ee6dbd20 \
  --out NEW_REPORT.json
```
