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

## Follow a sequence of field-scored rewrites

`select_sequential_field_rewrites` passes paid training feedback to a proposer, with separate rows for validation. Each strict minibatch improvement enters the parent pool. The scheduler can request complete validation grades to reproduce the native Pareto draw. The selector keeps the native full-round budget reserve and uses paired score bounds whenever the remaining replies cannot change an acceptance decision or the final ranking.

The archived Sol comparison matched native sequential GEPA's parent pools, minibatches, ordered later proposals, nominations, admission decisions, and all 480 held-out outcomes at each cap. The full cap included 190 recorded reflections across 87 replay paths. These paths use the original parent-linked proposal graph and historical prices.

| Search cap | Matched passes | Native → paired search reads | Native → paired total cost |
| --- | ---: | ---: | ---: |
| 12 | 382 / 480 | 2,880 → 1,962 | $29.003640 → $22.789632 |
| 24 | 382 / 480 | 3,502 → 2,814 | $35.633544 → $32.084040 |
| 40 | 382 / 480 | 4,108 → 3,463 | $46.811472 → $43.575840 |
| 56 | 382 / 480 | 4,108 → 3,463 | $46.811472 → $43.575840 |

The public deterministic fixture generates later rewrites from the errors in each selected parent's paid training replies. At cap 56, it matched all 19 later proposal inputs and outputs, including seven edits that changed the parent prompt. It preserved 314 of 324 held-out passes while reducing search reads from 672 to 532 and leaving admission reads at 525. The archived graph and deterministic fixture leave live proposal quality unverified. [Fixture receipt](sequential-field-feedback-results-v1.json)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.sequential_field_feedback
```

### Draw a parent from partial validation grades

The replay scheduler accepts `parent_bounds=True` for two distinct candidates and up to 32 validation cases. For each missing grade it considers the possible case winners and ties. It uses the paid grades to skip further reads only when every possible completion gives GEPA 0.1.4 the same parent and advances the random generator to the same state. That state also controls the subsequent training minibatches. The scheduler reads complete profiles outside this scope unless the larger-pool option below can certify a draw.

At the 56-read cap, the deterministic feedback fixture needed 518 search reads with this option, down from 532 with the complete-profile scheduler and 672 for native sequential GEPA. All three matched the 19 later proposal inputs and outputs, 525 admission reads, and 314 of 324 held-out passes. At cap 40, both CPO variants used 319 search reads and matched all outcomes. The fixture uses generated replies. [Fixture results](sequential-field-parent-bounds-results-v1.json)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.sequential_field_feedback --parent-bounds
```

## Reinvest saved reads

Set `reinvest_savings=True` to budget each additional round against paid evaluation reads. The selector reserves unread validation grades for every eligible parent. It then reserves the selected parent's missing training replies and a complete new child's training and validation replies. The same proposal limit and independent admission gate apply. The default keeps the original native round horizon.

At the shared 48-read search cap, the deterministic fixture gained 21 held-out passes across its two seed sets and cut counted calls from 2,224 to 2,021. Every path preserved or improved its holdout pass count and retained all matched critical passes. Seven paths used more calls. Counts include evaluations, proposal generation, and admission. Scores tied at caps 40 and 56. [Fixture results](sequential-field-paid-budget-results-v1.json)

| Fixture seed set at cap 48 | Native → CPO held-out passes | Native → CPO counted calls |
| --- | ---: | ---: |
| Published seeds | 299 → 310 of 324 | 1,133 → 1,041 |
| Replication seeds | 310 → 320 of 324 | 1,091 → 980 |

The Sol archive held at 382 of 480 passes for both policies. At cap 24, extra reflections raised the recorded cost from $35.63 to $38.24 despite fewer search reads. At cap 56, the number of reflections stayed at 190 and cost fell from $46.81 to $40.21. The read cap covers evaluations. Real proposal prices and fresh model quality remain unverified.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.sequential_field_feedback --paid-budget
```

## Reserve for proposal costs

Pass a `SequentialSearchBudget` as `price_budget` to enforce an advance search quote in integer units. Set a maximum charge per evaluation and supply up-front and settled charges for proposals. The selector holds enough for all unfinished validation, the next round's possible reads, and its proposal before starting the round. It settles each paid reply against the quote. The caller's evaluator and proposer enforce their upper bounds. Prepaid openings and independent admission have separate reserves.

On 240 archived Sol paths, both arms used the same 24-read ceiling, advance charge quotes, and reserves for opening and admission. The quotes used the highest recorded evaluation and reflection charges per task. The three spending levels corresponded to 16, 20, and 24 evaluation quotes plus the common opening. Each policy scored 382 of 480 at every level and stayed within its per-path spending ceiling.

| Evaluation quotes in the ceiling | Sequential GEPA cost | CPO cost | Pooled savings |
| --- | ---: | ---: | ---: |
| 16 | $29.00 | $25.56 | 11.9% |
| 20 | $30.94 | $27.36 | 11.6% |
| 24 | $31.57 | $28.17 | 10.8% |

At the largest ceiling, CPO funded 15 later reflections and cost more than GEPA on 15 paths. In the deterministic fixture under a shared 48-unit search quote, CPO gained 16 held-out passes and reduced total charge from 2,141 to 1,922 when a later proposal cost one unit. With four- and eight-unit proposals, it preserved the native score and used 1,848 units. These tests use archived or fixture prices. Live use requires provider-enforced upper bounds. [Fixture results](sequential-field-quote-results-v1.json)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.sequential_field_feedback --quoted-budget
```

### Combine the advance quote with partial parent grades

The recorded Sol replay compared the parent-draw proof under the same three advance quotes. Both arms matched all 1,440 individual held-out outcomes across the quotes. At the highest quote, CPO used 2,366 search reads and cost $26.68, compared with 3,276 reads and $31.57 for sequential GEPA. That is 15.5% lower pooled cost. CPO spent more on three of 240 paths. The replay used archived replies and prices.

Run the public fixture with the same two options. With one-unit reflections, CPO passed 609 of 648 held-out cases at a total charge of 1,883 units. Sequential GEPA passed 593 at 2,141 units. With four- or eight-unit reflections, both passed 593 and CPO used 1,802 units. [Fixture results](sequential-field-quote-parent-bounds-results-v1.json)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.sequential_field_feedback --quoted-budget --parent-bounds
```

The same parent option works with the evaluation-only cap. On the Sol archive at cap 24, this mode bought enough extra proposals that CPO cost $37.63 against sequential GEPA's $35.63, with the same number of passes. [Paid-read fixture results](sequential-field-paid-parent-bounds-results-v1.json)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.sequential_field_feedback --paid-budget --parent-bounds
```

## Verify

```sh
python -m pytest -q tests/unit/test_paired_field_rewrite.py tests/unit/test_sequential_field_rewrite.py tests/unit/test_gepa_parent.py
```

The tests enumerate all 65,536 field profiles for two prompts on four three-field cases with and without observed-charge ordering. They check the native result and verify that each paid read belongs to the complete native comparison. The Sol replay used the pinned GEPA 0.1.4 first minibatch and exact published control receipts. Two offline runs matched byte for byte. Fresh proposal generation and independent live confirmation remain unverified.

The parent-draw test checks all 729 two-candidate combinations of three grades on three validation cases and eight seeds against GEPA 0.1.4, including the generator state after each draw.

## Follow multiple same-parent batches

`select_batched_field_rewrites` keeps GEPA's full-read round horizon while evaluating only the replies needed for each strict gate. A round draws one parent and samples a training minibatch for each proposal from that parent. The selector adds the strict minibatch winners to the pool in order, removing duplicate winners within the round. Later proposals receive the same paid training feedback, including repetitions from the sampler's epoch padding. A repeated case uses the paid reply already in the cache. Independent admission runs after nomination.

Pass a `SequentialSearchBudget` as `price_budget` to fund each batch under an advance spending ceiling. Before asking for either proposal, CPO reserves all outstanding validation grades, the selected parent's unread training replies, and the maximum evaluation and proposal charges for every slot. It settles actual charges against these quotes. The caller's evaluator and proposer enforce the upper bounds. Shared opening and admission costs use separate reserves.

On 36 deterministic panels at the 76-read cap, CPO and native width-two GEPA matched the candidate pools, parents, minibatches, all 30 later proposal requests and outputs, admission, and all 648 held-out outcomes. Both passed 622. CPO reduced search evaluations from 1,658 to 1,179 and used the same 1,038 admission evaluations. Every paid CPO search reply also appeared in the native trace. Scripted replies exercise the schedule and evaluation savings. [Fixture results](batched-field-feedback-results-v1.json)

The recorded Sol replay matched batched GEPA on all 960 paths across four caps, including the reflection edges, nominees, admissions, and held-out outcomes. At cap 56 both methods used 186 recorded reflections on 88 paths and passed 380 of 480 held-out cases. CPO reduced search reads from 5,466 to 4,485. The historical charge, including the shared opening, recorded reflections, and admission, fell from $53.18 to $48.13. This 9.5% reduction applies to the recorded trajectories. Fresh provider performance remains unverified.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.batched_field_feedback
```

### Certify a parent draw for larger pools

`--frontier-bounds` extends the width-two benchmark to pools of three to seven distinct candidates on up to 32 validation cases. The proof enumerates the possible sets of highest-scoring candidates on each case. It includes every possible survivor set from GEPA pruning while allowing extra removal orders. The scheduler skips further reads when every considered outcome gives the same parent and the same random generator state. It pays for another grade when the proof is ambiguous and uses the native draw when it needs complete profiles.

At cap 76, the fixture saved another 22 reads, bringing CPO to 1,157 search reads against 1,658 for native batched GEPA. The Sol replay preserved the native schedule and every held-out outcome across 960 paths. At cap 56, the larger-pool proof lowered CPO's search reads from 4,485 to 4,388 and lowered the estimated total from $48.13 to $47.56. Native GEPA cost $53.18 at the same cap, so the pooled savings increased from 9.5% to 10.6% at archived rates. [Fixture results](batched-field-frontier-bounds-results-v1.json)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.batched_field_feedback --frontier-bounds
```
