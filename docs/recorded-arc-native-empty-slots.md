# Give native GEPA the same empty-slot information as CPO

This replay gives GEPA 0.1.4 the same finite proposal availability as CPO. It draws the native parent and all native minibatches first, then drops tasks beyond the number of remaining openings and recorded children of that parent. In a two-proposal round with one child left, GEPA evaluates the first minibatch only. It keeps its original validation, candidate selection, and round horizon. The ARC adapter uses GEPA’s default of proposing even after a perfect training minibatch, so the number of available proposals determines which native tasks can use them. [Prior CPO replay](recorded-arc-skip-empty-slots.md) · [Sealed result](recorded-arc-native-empty-slots-results-v1.json)

The full-round variants keep the published GEPA read and price reserves. The available-slot variants replace those reserves with a check after sampling. That check quotes uncached parent reads, a full child evaluation per retained task, and the later proposal charges, all before evaluation. An unaffordable nonempty round ends the search. The two variants separate the effect of skipping empty work from the effect of quoting only work that can proceed.

## Wider budget at the four-quote proposal price

| Policy | Held-out passes / 9,600 | Search and admission reads | Recorded evaluation cost | Modeled proposal cost |
| --- | ---: | ---: | ---: | ---: |
| CPO with empty-slot skip | 6,662 | 3,486 | $408.60 | $86.08 |
| Sequential GEPA with empty-slot skip, either reserve | 6,657 | 4,532 | $522.49 | $103.59 |
| Batched GEPA with empty-slot skip, either reserve | 6,523 | 4,597 | $531.43 | $96.29 |

CPO spent 21.8% less on recorded evaluations than sequential GEPA and 23.1% less than batched GEPA at this point. The paired score range was −3 to +13 against sequential GEPA and +110 to +171 against batched GEPA. Every GEPA skip variant matched its original held-out outcomes at all four price points. With the tighter 32-quote ceiling, the available-slot reserve retrieved 12 more children at the one-quote proposal price and seven more at the four-quote price in batched GEPA.

At 32 evaluation quotes and the four-quote proposal price, CPO gained 308 passes over both batched variants. Its combined recorded and modeled cost advantage was $0.86 against the cheaper full-round variant, down from $13.73 against the original GEPA control. That small margin depends on the modeled proposal price. The score ranges describe the same 80 recorded ARC problems, and the replay sent zero provider requests.

## Reproduce offline

From the source revision that added this receipt, use Python 3.12 with the pinned GEPA 0.1.4 wheel. The eight previously published arms matched their full path hashes at all four price points. Storage Guard measured 9.2 GiB free. The standing LAB exception covered a temporary source export and wheel expansion bounded at 0.1 GiB. The run blocked sockets and DNS and removed temporary resources after verification. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_lineage_quotes --match-native-empty-slots
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_lineage_quotes --match-native-empty-slots \
  --execute 1750ca92f685ed0841c93ef585b28d972f4fed98f9bae571d9072784300da256 \
  --out NEW_REPORT.json
```

The same empty-slot policy was also compared against native sequential GEPA on recorded Sol responses with a separate source holdout. [Sol transfer results](recorded-sol-empty-slots.md)
