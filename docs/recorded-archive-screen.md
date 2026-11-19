# Screening unused archive candidates

Mixed retrieval found useful candidates on earlier branches, but ordinary CPO often stopped with part of its evaluation and proposal budget unspent. This replay used the remainder to screen archive entries that search had yet to propose. [Earlier branch replay](recorded-archive-restart.md)

## Protocol

Each of 48 freshly seeded splits per task assigned three recorded cases each to training, validation, promotion, and holdout. CPO and the official sequential and batched GEPA 0.1.4 controls received the same mixed archive order and the same limits of 144 search evaluations and 16 proposal slots. CPO’s screen reused the same ordinary search prefix across arms.

- **Full screen** evaluated remaining validation rows for up to eight unused earlier candidates, in archive order.
- **Certified screen** used the same order with a limit of four or eight candidates. It stopped when paid observations proved a strict validation gain over the ordinary search winner, showed a loss on a protected critical case, or ruled out a strict gain within the remaining budget.
- **Ordinary mixed search** used the existing result directly.

Both screens stopped at the first validation gain that preserved the ordinary winner’s critical validation passes. A separate promotion panel then compared the selected challenger with the deployed incumbent. A rejected challenger kept the incumbent. Ticket’s ordinary validation was already perfect, so the screen made no additional calls. Each archive lookup, evaluation, and promotion observation was charged. [Certificate implementation](../cpo/challenger.py)

## Results

Each cell shows replay holdout passes and charged calls. Every task uses 144 replay holdout observations per method.

| Task | Ordinary CPO | Certified CPO, up to eight | Full CPO, up to eight | Sequential GEPA | Batched GEPA |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ticket | 144 / 144 | 144 / 144 | 144 / 144 | 144 / 144 | 144 / 144 |
| Warehouse | 131 / 436 | 131 / 580 | 131 / 684 | 131 / 746 | 131 / 746 |
| Outage | 91 / 977 | 109 / 1,338 | 109 / 1,554 | 96 / 1,518 | 98 / 1,650 |

The eight-candidate certificate matched every full-screen challenger, promotion decision, and final selection across all 144 splits. It halved outage screening evaluations from 432 to 216. Relative to ordinary CPO, it added 18 outage holdout passes and 18 promotions for 361 more calls within the original caps. The four-candidate screen added 11 passes for 238 more calls. On warehouse, ten candidates passed the eight-candidate screen and none passed independent promotion.

The eight-candidate policy earned more outage passes at lower cost than both GEPA controls. It missed one critical pass against sequential GEPA and two against batched GEPA, leaving the outage qualification gate unmet. The losses came from two seeded splits. On one, CPO retained the incumbent and batched GEPA promoted a challenger. On the other, CPO and both GEPA controls promoted different candidates.

Both sides had original provider holdout evidence for 31 of 48 outage splits against each GEPA control. On those matched records, certified CPO gained 63 pass observations over sequential GEPA and 54 over batched GEPA. Those counts reuse the original holdout rows across splits. The replay tests selection among recorded prompts. Fresh proposal quality and spending remain unmeasured. [Sealed per-task results](recorded-archive-screen-results-v1.json)

## Reproduce

Use the intact research archive and pinned GEPA dependency from the earlier replay.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -m benchmarks.recorded_archive_screen
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -m benchmarks.recorded_archive_screen \
  --execute PLAN_SHA256 --out result.json
```

The CLI verifies the earlier archive seal before printing the experiment seal. The two offline executions matched byte for byte. Raw provider replies remain in the research archive.
