# Order exact final validation by remaining family gain

`certify_family_ordered_validation_gain` uses the existing exact acceptance rule. When several net gains are still possible, the helper checks families with the fewest possible additional passes first, after accounting for cached replies. The certificate retains priority for cached outcomes and protected critical passes. When at most one net gain remains possible, any further miss rules out strict improvement, so the helper keeps the original order. [Helper](../cpo/family_ordered_validation.py) · [Exact certificate](../cpo/anchored_validation.py)

```python
from cpo.family_ordered_validation import certify_family_ordered_validation_gain

accepted = certify_family_ordered_validation_gain(
    rows, anchor_passes, evaluate, known=cached_challenger_passes,
)
```

The first experiment sorted ties by family headroom in every case. It saved 31 reads on scripted panels and added seven on the 240 recorded Sol paths. Each extra read came from outage. Preserving the original order among protected rows alone did not remove that difference. Skipping the reorder when only one net gain was still possible removed all seven extra reads. The final helper reproduced every Sol path byte for byte, including search costs, selected prompts, and held-out results. [Initial experiment](opening-final-validation-order-results-v1.json) · [Revised schedule](opening-final-validation-order-transfer-results-v1.json)

| Scripted cohort | Original schedule calls | Revised schedule calls | Holdout passes under each |
| --- | ---: | ---: | ---: |
| Pilot with original faults | 2,228 | 2,208 | 648 of 648 |
| Pilot with shifted faults | 2,247 | 2,236 | 648 of 648 |
| New panels with original faults | 2,260 | 2,244 | 648 of 648 |
| New panels with shifted faults | 2,235 | 2,219 | 648 of 648 |

The new panels used four unseen seeds and the same two native GEPA controls. The revised schedule preserved every nomination, admission, and matched holdout reply of the ordinary certificate. Exhaustive tests covered 4,096 combinations of anchor, challenger, and cached replies for each schedule. The helper is opt-in. These measurements use recorded and scripted replies, and fresh provider costs remain open.

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path. The benchmark invokes the new helper at the existing staged certificate boundary.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_final_validation_order_transfer
PYTHONHASHSEED=0 python -B -m benchmarks.opening_final_validation_order_transfer \
  --execute cbc627f49e7601d323ce8b39172d3ad508a85cb3634ea9f4ada74cdf140153e9 \
  --out NEW_REPORT.json
```

Both scripted and recorded experiments reproduced byte for byte in two runs with sockets and DNS blocked. Nine focused tests passed, and an isolated wheel build imported and executed the new helper. The separate Sol archive is required to reproduce the recorded portion. [Transfer benchmark](../benchmarks/opening_final_validation_order_transfer.py) · [Sealed results](opening-final-validation-order-transfer-results-v1.json)
