# Resuming validation with unspent evaluations

`cpo.challenger.certify_challenger` continues a single challenger’s validation from a partial record. It requires the exact incumbent results on the same panel. The challenger must prove a strict gain in total passes and preserve every critical pass measured for the incumbent. The function skips cached cases, prioritizes protected rows, and stops when promotion is proved, ruled out, or impossible within the fresh-evaluation limit. A budget stop returns the retained evidence and the minimum number of new observations that could still certify promotion. [Validator](../cpo/challenger.py)

```python
from cpo.challenger import certify_challenger

result = certify_challenger(
    validation_rows,
    incumbent_outcomes,
    evaluate_challenger,
    metric_limit=remaining_evaluations,
    observed=previous_challenger_outcomes,
)
if result.status == 'promote':
    selected_prompt = challenger_prompt
```

Use the same prompt, rows, and evaluator when carrying `result.observations` into a later call. Bounds apply to the fixed validation panel. The evaluator returns a CPO `Observation` for each requested row.

## Component search

All continuation arms used the same ordinary, dependency-aware CPO prefix. The search could spend its entire 96- or 144-evaluation cap. After it stopped, the finish policy considered partially evaluated candidates that stopped on a round budget. It ranked feasible candidates by the minimum number of fresh observations needed for promotion, then by known passes. The hint policy tried an unmeasured edit suggested by an incompatible diagnostic. The matched alternative substituted an unsupported edit from the same parent. The combined policy tried finishing first and fell back to the hint if no promotion occurred. It stopped after one promotion so every attempted challenger faced a fully measured incumbent.

The test used 40 new seeds, four profiles, and two caps. Each arm scored 11,520 held-out cases in total. These counts include the same routing cases with scope declared and withheld, as well as repeated profiles at both caps. Costs include distinct evaluations and scripted proposal slots. A finish attempt reuses an existing proposal.

| Method | Held-out passes | Search calls |
| --- | ---: | ---: |
| Ordinary CPO with dependencies | 8,090 | 32,081 |
| Finish an interrupted candidate | 8,385 | 32,884 |
| Try a diagnostic hint | 8,145 | 32,295 |
| Try a matched alternative | 8,096 | 32,197 |
| Finish, then try a hint | 8,429 | 33,062 |
| Full-budget component-only CPO | 8,317 | 32,738 |
| Official GEPA with dependencies | 7,131 | 32,885 |
| Official GEPA with dependencies and native merge | 7,220 | 32,510 |

Finishing accounted for 70 promotions. The combined schedule earned nine more from hints and gained 339 held-out passes over ordinary dependency-aware CPO. It preserved every critical holdout pass that baseline achieved. It spent 981 more calls, including 965 fresh evaluations. Every trial stayed within its original evaluation cap. The combined schedule cleared both GEPA controls on the local panels and missed the critical-case gate on the contextual panels. The validator is opt-in, and the combined schedule remains a benchmark. [Sealed component results](component-spare-validation-results-v1.json)

## Recorded model scores

On each archived correctness matrix, 40 seeded trials selected a pair of candidates and preloaded one third of the challenger’s validation results. The certificate matched complete validation in every trial. The matrices contain binary scores and have no critical labels. The separate component fixture and exhaustive unit tests exercise critical-case protection. [Matrix provenance](fixed-pool.md) · [Sealed replay totals](challenger-recorded-replay-v1.json)

| Dataset | Fresh lookups | Full validation of remaining rows |
| --- | ---: | ---: |
| Abstract algebra | 532 | 640 |
| AIME | 188 | 280 |
| ARC-AGI | 214 | 400 |
| **Total** | **934** | **1,320** |

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
PYTHONHASHSEED=0 python -m benchmarks.component_spare_validation
PYTHONHASHSEED=0 python -m benchmarks.component_spare_validation --execute PLAN_SHA256 --out result.json

python -m benchmarks.challenger_replay --dataset aime --matrix MATRIX_PATH
python -m benchmarks.challenger_replay --dataset aime --matrix MATRIX_PATH --execute PLAN_SHA256 --out replay.json
```

Use the seal from the corresponding preview. Both evaluations used deterministic inputs and blocked network access. The recorded replay measures a validation procedure on existing scores. It does not measure fresh proposal generation.
