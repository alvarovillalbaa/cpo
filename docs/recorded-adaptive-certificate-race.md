# Reorder challengers during the first validation certificate

The first-certificate policy follows the seeded roster and qualifies the first challenger whose paid validation passes exceed the incumbent's complete validation score. This replay lets the race switch challengers after any validation reply. It keeps the same incumbent, available prompts, strict validation certificate, complete training reserve, and one independent qualification attempt. [Original certificate race](recorded-first-training-certificate.md) · [Replay runner](../benchmarks/recorded_adaptive_certificate_race.py)

The scheduler estimates a candidate's remaining cost to settle its certificate and divides that cost by the estimated chance of proving a gain. The estimate uses the candidate's paid pass count and other paid replies on each unread case. The model rounds probabilities to quarter bins and treats future grades as independent. A candidate's actual paid grades give the exact acceptance and rejection bounds, and can rule out a certificate at any time. One version assigns each reply unit cost. The price version uses the candidate's mean paid validation price, falling back to the incumbent's price until that candidate replies. AIME has unit prices in both versions.

| Archive and roster | Seeded race passes / lookups | Adaptive by lookups | Adaptive by recorded price |
| --- | ---: | ---: | ---: |
| AIME, original, four challengers | 490 / 912 | 486 / 951 | 486 / 951 |
| AIME, original, eight challengers | 487 / 1,066 | 482 / 1,120 | 482 / 1,120 |
| AIME, rotated, four challengers | 4,077 / 6,737 | 4,070 / 6,821 | 4,070 / 6,821 |
| AIME, rotated, eight challengers | 4,082 / 8,191 | 4,073 / 8,528 | 4,073 / 8,528 |
| ARC-AGI, original, four challengers | 1,496 / 1,402 | 1,539 / 1,430 | 1,526 / 1,450 |
| ARC-AGI, original, eight challengers | 1,496 / 1,402 | 1,539 / 1,470 | 1,531 / 1,534 |
| ARC-AGI, rotated, four challengers | 13,731 / 7,580 | 13,750 / 7,708 | 13,710 / 7,846 |
| ARC-AGI, rotated, eight challengers | 13,755 / 8,346 | 13,817 / 8,699 | 13,770 / 8,834 |

On eight-challenger rotated ARC-AGI, the lookup-based race changed 16 deployments, gaining 79 and losing 17 held-out passes. It added 353 lookups and $65.24 at recorded prices over the seeded race. It beat the strongest affordable GEPA setting by 49 passes under both lookup and price budgets, with a paired 95% case range of +4 to +93. The price version used 135 more lookups than the lookup version and saved $6.35, while losing 47 passes. Its matched GEPA range crossed zero. [All paired outcomes, rival costs, and changes](recorded-adaptive-certificate-race-results-v1.json)

On eight-challenger rotated AIME the adaptive race switched candidates 2,631 times, changed ten deployments, and added 337 lookups while losing nine passes. It did worse at every AIME width and start. The earlier qualification-only ARC-AGI policy scored higher on fewer lookups on both rotations. The evidence favors keeping the adaptive race out of the default policy. [Qualification-only ARC-AGI results](recorded-calibrated-training-route.md#frozen-rule-on-the-math-archives)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two network-denied replays matched byte for byte, including all seeded and native cost frontiers. An independent check verified all 3,040 deployments against the complete validation, training, and qualification margins. All 48 targeted tests passed, including exhaustive small-pool certification, protected validation rows, and reserve limits. The CLI rejected the prior seal. The public selector parity receipt and sealed live-plan preview reproduced. Storage Guard measured 2.9 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_adaptive_certificate_race
python -B -m benchmarks.recorded_adaptive_certificate_race \
  --execute 56c96c2a91d6bed67495694ea488bd046faa23d589cf6908f3d8c57ab8110d85 \
  --out NEW_REPORT.json
```
