# Qualifying a second recorded archive candidate

The archive screen missed three critical passes against the two official GEPA controls. On one split, CPO’s challenger tied batched GEPA on the three validation rows and failed to improve on the separate promotion panel. On the other, the selected prompts agreed on every training, validation, and promotion row, including field scores, and diverged on the holdout. The first case motivated a second-challenger trial. The second illustrates the limited evidence available before promotion. [Archive screen](recorded-archive-screen.md)

## Protocol

The recorded replay used 64 new seeded splits per task. Each split assigned three cases each to training, validation, promotion, and holdout. All methods inherited the same recorded candidate graph and mixed archive order. The CPO variants shared the certified eight-candidate screen as a prefix.

- **Single challenger** used the existing screen winner and one independent qualification attempt.
- **Rescue** nominated a second candidate that preserved every nominal validation pass of the first. It reused paid observations first and charged each new lookup. If the first challenger failed independent qualification, the second could use the remaining allowance. Both shared the original six-evaluation qualification cap.
- **Paired qualification** used the same nomination. When enough budget remained, it measured both challengers completely against one paid incumbent panel and chose the larger qualified gain. A tie kept the first challenger. A strict gain and preservation of each incumbent critical pass were required. When the full pair could not be funded, this arm used the rescue policy.

Search retained its limit of 144 evaluations and 16 proposal slots. All arms stayed within 150 combined search and qualification evaluations, so the paired arm could spend up to nine qualification evaluations only from unused capacity. The nomination skipped cases with a perfect deployed validation record. The GEPA controls used the original single-challenger promotion policy. [Challenger certificate](../cpo/challenger.py)

## Results

Each cell shows replay holdout passes and total charged calls across 64 splits. The splits reuse 12 archived cases per task.

| Task | Single challenger | Rescue | Paired qualification | GEPA sequential | GEPA batched |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ticket | 192 / 192 | 192 / 192 | 192 / 192 | 192 / 192 | 192 / 192 |
| Warehouse | 176 / 705 | 176 / 1,072 | 176 / 1,084 | 176 / 1,009 | 176 / 1,009 |
| Outage | 153 / 1,967 | 153 / 2,887 | 158 / 2,985 | 121 / 2,363 | 121 / 2,439 |

Rescue changed no selections. Paired qualification found four additional outage promotions and five extra holdout passes without a matched critical loss against the single-challenger arm. It spent 1,018 more calls, including 579 nomination evaluations. Neither qualification variant repaired the two original outage failure splits in a retrospective check. Both CPO qualification variants still missed one critical pass against each GEPA control on the new splits. The extra spending and repeated critical misses do not support replacing the single-challenger policy.

On the available original provider holdout, paired CPO gained 189 pass observations against sequential GEPA and 180 against batched GEPA across 49 and 47 matched outage splits. Those splits reuse the same original holdout cases. This replay tests selection among recorded candidates. It omits fresh proposal generation. [Sealed results](recorded-archive-qualification-results-v1.json)

## Reproduce

Use the intact research archive and pinned GEPA dependency from the earlier replay.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -m benchmarks.recorded_archive_qualification
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -m benchmarks.recorded_archive_qualification \
  --execute PLAN_SHA256 --out result.json
```

Use the seal printed by the preview. The full result includes each nomination, observed qualification path, and held-out outcome. Two runs with network access blocked produced byte-identical reports.
