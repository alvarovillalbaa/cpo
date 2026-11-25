# Reorder narrow validation while preserving the full decision

The conditional tail saved lookups and lost accuracy on the original ARC-AGI start. This experiment keeps the full funded uniform panel and changes only the order of its reads. All variants use exact bounds to settle the winner and carry the incumbent's and finalist's full counts into the same independent qualification. The change applies to noncritical uniform rounds with two challengers and three to six funded validation cases. [Math tail results](validation-routed-tail-math.md) · [Runner](../benchmarks/validation_routed_exact_order.py)

- **Independent order** reuses the earlier Beta-prior planner, which orders the next prompt by expected remaining reads.
- **Prepaid order** feeds that planner the incumbent grades already purchased by the opening route before asking it for another grade. It uses the original cache and charges each reply once.
- **Paired order** also uses each case's observed partner grades to estimate the next grade. It averages the prompt's current Beta estimate with the mean of paid grades on that case. The earlier planner estimates the cost after either outcome. The probability model determines read order. Only exact observed grades and their bounds decide the result.

The replay measures 760 AIME and ARC-AGI episodes and 64 Promptolution episodes with the frozen partitions and rosters. It verifies the entire sequence of nominees, deployments, and nonvalidation replies against uncapped routing for each episode. Previously reported controls and math layouts must reproduce. [Earlier independent planner](promptolution-settled-episode-read-order.md) · [Sealed results](validation-routed-exact-order-v1.json)

| Archive | Held-out passes in each arm | Uncapped routed lookups | Independent order | Prepaid order | Paired order |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIME, original | 498 | 601 | 600 | 600 | 604 |
| AIME, rotated | 4,072 | 4,658 | 4,664 | 4,664 | 4,711 |
| ARC-AGI, original | 1,432 | 774 | 776 | 776 | 815 |
| ARC-AGI, rotated | 13,580 | 3,212 | 3,213 | 3,213 | 3,302 |
| Promptolution GSM8K | 2,440 | 850 | 851 | 851 | 873 |
| Promptolution SST5 | 1,439 | 1,598 | 1,600 | 1,600 | 1,623 |

Explicitly initializing the planner with the paid routing prefix produced the same total cost as independent ordering on every group. The two variants saved one lookup on original-start AIME and spent 11 more lookups across the measured mix than uncapped routing. The paired variant spent 235 more lookups. On original-start ARC-AGI, the exact orders retained all 35 passes lost by stall-only continuation. They cost at least two lookups more than uncapped routing, so this family did not recover the stall-only cost saving at the original accuracy. Historical evaluator charges increased on both ARC-AGI groups under every variant. The packaged routing continues to use the original read order.

## Reproduce offline

Use Python 3.12, the pinned GEPA 0.1.4 wheel, and the Promptolution corpus from the earlier comparison. Run the benchmark without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.validation_routed_exact_order \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 7814daffddd362c558869d2f99474110aabda329601eedb4dab093107af52f6c \
  --out NEW_REPORT.json
```

Two socket-blocked replays matched byte for byte at SHA-256 `f0a2f1111131b7ff610307ca4a18c70f0ccfded3b606103e8303bb9e21aa8cc0`. All 49 focused tests and four subtests passed, including every Boolean four-case panel for the two new ordering rules. The CLI rejected a stale seal and an existing output path. The replays sent zero provider requests. Storage Guard measured 8.4 GiB free. The export, pinned wheel overlay, corpus copy, and publication worktree used 123 MiB under the standing LAB exception. [Focused test](../tests/unit/test_validation_routed_exact_order.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
