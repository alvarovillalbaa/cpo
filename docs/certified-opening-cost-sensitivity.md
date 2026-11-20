# Reprice certified opening validation

Certified opening CPO and the fixed-opening GEPA control selected the same prompt on all 240 archived Sol paths. All 480 paired scores agreed, including every critical case. Both policies passed 382. The original attributed costs were $20.842344 for CPO and $23.456712 for GEPA. [Parent replay](certified-opening-validation.md)

| Scope | One charge per reply | Separate charges by policy |
| --- | ---: | ---: |
| All paths | 10.46–11.54% | 8.74–13.20% |
| First seed set | 10.48–11.67% | 8.80–13.30% |
| Second seed set | 10.42–11.41% | 8.68–13.10% |
| Ticket | 10.69–11.46% | 9.78–12.35% |
| Warehouse | 13.32–15.34% | 10.93–17.61% |
| Outage | 7.17–7.24% | 5.66–8.73% |

Under shared pricing, the pooled saving clears the 10% gate for every observed price assignment. If each policy can incur a different price for the same prompt and case, the conservative pooled lower bound falls to 8.74%. Outage has the smallest saving under both assumptions. The shared proposal cost stays fixed in both calculations. The archive records stable grades across repeated replies for all eligible cells.

The bundled data groups cells with identical usage counts and price endpoints. It contains no prompts, case identifiers, or raw replies. For the shared-charge interval, the calculator minimizes and maximizes the ratio of CPO to GEPA cost using exact rational arithmetic. At a trial ratio, the sign of each cell's contribution selects its price endpoint. When the recomputed ratio is unchanged, the endpoints are optimal. Giving CPO the highest eligible prices and GEPA the lowest gives the lower bound for separate charges. Reversing those assignments gives the upper bound.

These intervals describe cost under the archived replies and observed charge ranges. Fresh model behavior and charges remain unverified. [Cost terms](../benchmarks/data/certified-opening-cost-terms-v1.json) · [Calculator](../benchmarks/certified_opening_cost_sensitivity.py)

```sh
python -B -m benchmarks.certified_opening_cost_sensitivity
python -m pytest -q tests/unit/test_certified_opening_cost_sensitivity.py
```
