# Prove paired rewrite gains with field credit

The [paired rewrite selector](recorded-paired-rewrite.md) now has a field-scored variant for a supplied rewrite. On all 240 typed Sol replay paths, it matched native fixed-rewrite GEPA's nomination, independent admission, and every held-out result. It read a strict subset of the native search replies on every path. The same 382 of 480 held-out uses passed. [Transfer report](recorded-paired-field-rewrite-results-v1.json) · [Implementation](../cpo/paired_field_rewrite.py)

| Policy | Search reads | Admission reads | Attributed cost at archived rates |
| --- | ---: | ---: | ---: |
| Native fixed-rewrite GEPA | 1,920 | 793 | $23.456712 |
| CPO opening dominance | 1,383 | 793 | $19.915032 |
| CPO paired field rewrite | 1,253 | 793 | $19.371768 |

Paired field rewrite cost **17.41% less** than native fixed-rewrite GEPA and **2.73% less** than opening dominance in this replay. It reduced the outage search count from 640 to 453 against the native control. The estimates include the common supplied opening and unchanged admission costs. [Opening dominance replay](opening-dominance.md)

## Savings across archived charges

The token charges varied across recorded replies for the same prompt and case. With one charge per case and prompt shared across policies and seed sets, pooled savings range from **17.30% to 17.49%**. Allowing each policy to incur a distinct charge expands the range to **14.85% to 19.86%**. The shared opening retains its original price in both calculations.

| Scope | Savings with separate charges |
| --- | ---: |
| Ticket | 17.43–20.46% |
| Warehouse | 15.02–23.04% |
| Outage | 13.00–15.86% |

Every task and both seed sets clear the 10% cost gate at the least favorable archived prices. The bounds use the same nominations, admission replies, and 480 matched held-out scores as the replay. Fresh replies can have different charges and scores. The bundled terms are grouped counts and price endpoints. [Grouped cost terms](../benchmarks/data/paired-field-rewrite-cost-terms-v1.json)

```sh
python -B -m benchmarks.certified_opening_cost_sensitivity \
  benchmarks/data/paired-field-rewrite-cost-terms-v1.json
```

## Opt in to observed-charge ordering

`select_paired_field_rewrite` accepts an optional `observed_charge` callback. The evaluator can attach usage to each observation and the callback supplies the charge in a consistent integer unit. The selector asks for the charge after evaluation and uses it to prioritize the remaining full-validation reads. A missing charge or a zero cumulative charge for either prompt uses the estimated gain per read. The minibatch gate, native float comparisons, and admission contract retain their existing behavior.

```python
from cpo.paired_field_rewrite import select_paired_field_rewrite

nominee = select_paired_field_rewrite(
    incumbent, rewrite, validation_rows, minibatch_ids, evaluate,
    observed_charge=lambda _prompt, _row, reply: reply.feedback.get("charge_microusd"),
)
```

On the 240 Sol paths, this order reproduced every decision and held-out result while reducing search reads from 1,253 to 1,228 and attributed cost from $19.371768 to $18.736560. Both seed sets cost less. Fifteen individual paths cost more. On two complete Luna validation panels, the same rewrite nominations went from 39 to 28 reads and from $0.034427 to $0.024452, including the shared openings. Luna qualification remains unverified. Row-paired ordering is the default.

## Reproduce the path-level cost bound

In the Sol archive, charge-aware ordering retained a **17.40% pooled savings floor** against fixed-rewrite GEPA when each path and policy could incur separate charges within the observed ranges. Warehouse had the weakest task floor at 15.96%. The pooled cost margin at the 10% gate was $1.706069 for charge-aware and $1.117901 for row-paired. These figures use the archived replies and fixed shared opening charges.

The bundled data consists of anonymous grouped read counts, price endpoints, and observed cost pairs. The verifier recomputes the bounds and checks which extrema the recorded charges attain. The original archive replay established the underlying read sets and nominations before export. From a source checkout, run the calculation using the bundled data and the Python standard library. [Grouped path charges](../benchmarks/data/paired-field-path-charge-costs-v1.jsonl)

```sh
python -B -m benchmarks.path_local_charge_bounds
```

## How the proof handles score ties

Native GEPA compares exact passes before matched fields by giving one exact pass more weight than all possible partial credit. Across the two gates, the proof caches paid replies and bounds the integer score difference from the known credits and remaining field capacities. When the possible integer margin is strictly positive or negative, the proof can stop if the margin exceeds a conservative bound for native float rounding.

An integer tie can still advance under native arithmetic. With seven fields across four validation cases, scores proportional to `1 + 5` and `0 + 6` have equal integer totals. After the native division by 39, their floating-point sums differ. A focused test verified that native GEPA and the paired selector both advance the latter rewrite. A gate with a possible tie reads the needed replies and applies the native comparison order, including cached-before-fresh validation scores. The same complete comparison applies when the early rounding bound is unavailable.

## Verify

```sh
python -m pytest -q tests/unit/test_paired_field_rewrite.py
```

The tests enumerate all 65,536 field profiles for two prompts on four three-field cases with and without observed-charge ordering. They check the native result and verify that each paid read belongs to the complete native comparison. The Sol replay used the pinned GEPA 0.1.4 first minibatch and exact published control receipts. Two offline runs matched byte for byte. Fresh proposal generation and independent live confirmation remain unverified.
