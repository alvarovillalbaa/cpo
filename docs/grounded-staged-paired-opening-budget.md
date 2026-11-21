# Bound paid requests by shared paired-opening samples

The revised seal reduces the paired-opening development ceiling from **2,232 to 1,596 physical requests**. The model, prompts, arms, case splits, logical limits, and scoring rules are inherited from the original paired-opening plan. [Original protocol](grounded-staged-paired-opening.md) · [Portable budget plan](grounded-staged-paired-opening-budget-plan-v1.json)

| Role | Original ceiling | Shared-sample ceiling | Basis per task |
| --- | ---: | ---: | --- |
| Reflection | 48 | 48 | Original reflection allowance |
| Evaluation | 852 | 612 | Three dynamic arms at 56 each, plus 36 validation cells shared by the fixed arms |
| Admission | 576 | 288 | Up to six distinct prompts on eight cases with two repeats |
| Development scoring | 756 | 648 | Up to six distinct prompts on 18 cases with two repeats |

The fixed arms evaluate only the incumbent and the two shared opening prompts on the 12 validation cases. The dynamic arms may each qualify one additional prompt. Identical evaluations and admissions share the same request key. The scoring loop groups identical prompts before it sends a request. The journal enforces the case split, canonical schema, repeat range, and per-arm prompt scopes before dispatch. [Budget enforcement](../benchmarks/grounded_staged_paired_opening_budget.py) · [Boundary tests](../tests/unit/test_grounded_staged_paired_opening_budget.py)

Confirmation counts the actual distinct selected prompts for each task in the replayed development archive and multiplies that count by eight confirmation cases and two repeats. It can require at most 288 requests. The bound includes the selected-prompt and archive hashes. The fixture with two distinct prompts per task quoted and used exactly 96 requests.

Both SDK mock development archives preserved the original provider-wire hashes, attributed search costs, and paired-opening outcomes. Each resumed at request 41 and reproduced its uninterrupted archive byte for byte. The lower ceiling applies to the proposed trial. Live inference and effectiveness remain unverified.

A subsequent fixture replay measured how many scoring requests could be omitted once the paired-opening gate became impossible. [Early rejection replay](grounded-staged-paired-opening-futility.md)
