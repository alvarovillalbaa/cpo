# Compare two validation-proven nominees on training

The qualification-first CPO policy considers a paid validation runner-up only if the primary nominee fails training. This replay lets the runner-up compete when both have a proven validation gain. It ranks each by the smaller of its proved validation gain and exact training gain. The primary keeps ties. If the primary proves enough training gain to reach the runner-up's maximum possible rank, the runner-up needs no training reads. The comparison runs only when the original search cap funds a complete training check for both contenders. The selected prompt still faces one independent qualification. [Previous training proofs](recorded-expected-training-order.md) · [Replay runner](../benchmarks/recorded_corroborated_nomination.py)

The replay kept all original validation reads, roles, rosters, and GEPA cost frontiers. Outside the funded two-candidate comparison, it reproduced the original trace, costs, and deployment exactly. After each selection on the affected trials, a separate diagnostic uses all archived training and qualification replies to determine eligibility. It then picks the best held-out score among the incumbent and the eligible pair. It assigns no price to those extra proofs. This gives a ceiling on gains from changing only which of the same paid offers qualifies, or retaining the start.

| Archive and roster | Original passes / lookups | Paired training rank passes / lookups | Changed deployments | Maximum additional passes over original with hindsight |
| --- | ---: | ---: | ---: | ---: |
| AIME, original, four challengers | 489 / 1,160 | 489 / 1,165 | 0 | 6 |
| AIME, original, eight challengers | 485 / 1,604 | 485 / 1,611 | 0 | 7 |
| AIME, rotated, four challengers | 4,078 / 8,536 | 4,078 / 8,561 | 0 | 11 |
| AIME, rotated, eight challengers | 4,073 / 12,115 | 4,073 / 12,157 | 0 | 20 |
| ARC-AGI, original, four challengers | 1,561 / 1,844 | 1,565 / 1,923 | 1 | 10 |
| ARC-AGI, original, eight challengers | 1,578 / 2,041 | 1,582 / 2,136 | 1 | 10 |
| ARC-AGI, rotated, four challengers | 13,761 / 8,277 | 13,759 / 8,374 | 5 | 28 |
| ARC-AGI, rotated, eight challengers | 13,822 / 9,703 | 13,820 / 9,825 | 5 | 28 |

The new rule changed 12 deployments across 1,520 trials and increased costs in all eight settings. At the eight-challenger ARC rotation, five changes gained eight passes and lost ten. The replay added 122 lookups and $14.96 at recorded evaluator prices. Its paired case-resampled margin against the best affordable GEPA settings was −7 to +95 by lookups and −10 to +80 by historical cost. [Sealed results and all cost comparisons](recorded-corroborated-nomination-results-v1.json)

On the eight-challenger AIME rotation, hindsight recovered at most 20 passes on eight of the 94 eligible trials. The resulting ceiling of 4,093 exceeds the affordable GEPA score of 4,080. On the original AIME start, the eight-challenger ceiling was 492, below the 500 passes from keeping the start. The rotated ARC eight-challenger ceiling added 28 passes across ten of 48 eligible trials. These ceilings use held-out answers and free proofs. The paid ranking rule did not recover the headroom, and the replay gives no reason to adopt it.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two socket- and DNS-blocked replays matched byte for byte. All 40 targeted tests passed from a clean export, including 784 exact ranking combinations, a funded runner-up that replaces the original nominee, and fallback when the reserve is insufficient. The CLI rejected the earlier seal. The public selector parity receipt and ordered live-plan preview reproduced exactly. Storage Guard measured 2.9 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_corroborated_nomination
python -B -m benchmarks.recorded_corroborated_nomination \
  --execute 22b28ec11ea7594fd5f506f813def648dd254fbb224a25a268708b1574738d29 \
  --out NEW_REPORT.json
```
