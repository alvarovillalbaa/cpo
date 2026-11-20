# Route staged repairs from remaining validation failures

The [first-witness confirmation](opening-staged-witness-transfer.md) found that every chain with a matched critical loss stopped after a later batch of passing training probes. This experiment checks the current instruction on the opening’s original validation misses before buying another batch. It stops at the first remaining miss, then uses the input features of that case to rank unused training rows and earlier training witnesses. The proposer receives only the training observations. When no opening miss remains, the cycle proceeds to full validation without another training batch.

The search cap stays at 56 lookups per panel. The router can read up to four training probes per later stage and stops at the first observed failure. It reserves the full final validation panel. Checks on the final instruction count toward that panel. The final instruction still needs a strict gain and must preserve every protected critical pass and family score before independent qualification. [Runner](../benchmarks/opening_validation_routing.py)

## Confirmation

The benchmark reproduced the previous controls and added 36 disjoint scripted panels. Both fault modes use the same new inputs. The shifted mode changes the faulty entries and protects cases that exercise them. Each cell gives exact holdout passes out of 648 and total counted calls.

| Method | Original faults | Shifted faults |
| --- | ---: | ---: |
| Shorter opening batch | 632 / 2,658 | 607 / 2,675 |
| Validation-guided routing | 648 / 2,661 | 646 / 2,702 |
| Sequential GEPA | 568 / 2,920 | 564 / 2,963 |
| Batched GEPA | 527 / 2,642 | 512 / 2,693 |

Validation-guided routing passed the sequential GEPA gate and preserved every matched critical pass against both GEPA controls in both modes. It also preserved every holdout pass of the shorter opening batch. Against batched GEPA it gained 121 and 134 passes while using 19 and nine more calls, respectively, so the batched cost gate still failed. On the earlier shifted panels it reduced the 13 matched critical losses against sequential GEPA to zero. The earlier ordinary panels retained one matched critical loss. [Sealed results](opening-validation-routing-results-v1.json)

## Reproduce offline

Use GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_validation_routing
PYTHONHASHSEED=0 python -B -m benchmarks.opening_validation_routing \
  --execute fd19ee6ce143e9a22bf287f74c43f2150e5f161b9a7853a17966fb91d99df528 \
  --out NEW_REPORT.json
```

Two socket- and DNS-blocked replays matched byte for byte. Each covered 72 scripted input panels, 144 panel and mode combinations, and 288 native GEPA paths. Nineteen focused tests passed, including a check that the validation rechecks never reach the proposer. The runner rejected an altered seal and preserved an existing report. Storage Guard measured 4.5 GiB free and the 29.6 MB scratch export was removed under the standing LAB exception. Live qualification remains pending. [Verification receipt](opening-validation-routing-verification-v1.json)

## Qualification order pilot

On the same confirmation panels, a pilot used the existing paired certificate with critical cases first and a seeded family-balanced order within the critical and ordinary groups. It preserved the held-out pass totals. CPO used 209 fewer qualification calls under the original faults and 247 fewer under shifted faults. Changing only CPO’s order cleared both cost gates. Sharing the order with both GEPA controls also reduced their costs.

| Shared qualification schedule | Original faults passes / calls | Shifted faults passes / calls |
| --- | ---: | ---: |
| Validation-guided CPO | 648 / 2,452 | 646 / 2,455 |
| Sequential GEPA | 568 / 2,714 | 564 / 2,734 |
| Batched GEPA | 527 / 2,437 | 512 / 2,467 |

Under the shared order, CPO cleared both gates with shifted faults and finished 15 calls above batched GEPA with the original faults. This comparison reused the same inputs after the routing experiment. [Paired certificate](../cpo/paired_qualification.py) · [Family-balanced ordering](../cpo/optimizer.py)
