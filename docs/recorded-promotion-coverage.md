# Critical cases on the promotion panel

The prior replay found candidates that looked equally good on the available pre-holdout cases and behaved differently on critical holdout cases. This test reallocated already available critical rows between validation and promotion while keeping training and holdout fixed. [Earlier qualification replay](recorded-archive-qualification.md)

## Protocol

Each task contains 12 archived cases. The trial enumerates all 220 possible three-case holdouts. For each, a fixed seed assigns the other nine cases to three equally sized panels. The same training panel is used across all arms. The shuffled control retains the original validation and promotion assignment. The one-critical and two-critical policies swap cases to meet their respective promotion floors where possible, reserving one critical validation case if at least two are available across both roles. The allocation uses only the archived critical labels.

CPO uses the certified eight-candidate archive screen. Official sequential and batched GEPA 0.1.4 use the same mixed proposal graph. All arms retain the 144-evaluation and 16-proposal search caps and the six-evaluation independent promotion cap. Promotion requires a strict exact gain over the incumbent and preservation of its critical passes on that panel.

## Results

Each cell gives exact replay holdout passes and total charged calls. The 660 holdout observations per task reuse recorded cases. All possible holdouts are covered, with one fixed assignment of the other roles per holdout.

| Task | CPO shuffled | CPO one critical | CPO two critical | Sequential GEPA two critical | Batched GEPA two critical |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ticket | 660 / 660 | 660 / 660 | 660 / 660 | 660 / 660 | 660 / 660 |
| Warehouse | 605 / 2,379 | 605 / 2,161 | 605 / 2,000 | 605 / 2,767 | 605 / 2,767 |
| Outage | 486 / 6,106 | 486 / 6,050 | 490 / 6,253 | 425 / 7,071 | 424 / 7,397 |

Both floors eliminated the 22 outage promotion panels that had no critical case under shuffled assignment. Targeting two critical cases gained four exact outage passes for 147 additional calls relative to shuffled CPO. On warehouse, it preserved all passes and saved 379 calls.

The two-critical policy gained 65 and 66 outage holdout passes and saved 818 and 1,144 calls against GEPA under the same panel allocation. It missed two critical pass observations against sequential GEPA and four against batched GEPA. The shuffled comparison missed two and three respectively. In three of the six paired loss observations under the two-critical allocation, the CPO and GEPA prompts had identical archived exact and field results across all nine cases outside holdout. The outage qualification gate remains unmet. [Sealed per-task totals](recorded-promotion-coverage-results-v1.json)

The result shows how much this recorded case bank can tell us about promotion coverage. A replay with fixed proposals cannot establish how fresh candidates would behave.

The follow-up restored the individual fields behind the recorded scores. Protecting those fields at promotion changed no selection and left all six matched loss observations. [Field preservation replay](recorded-field-preservation.md)

Distributing cases across policy categories added 17 outage passes with the same critical quota and left matched critical losses against both GEPA controls. [Policy coverage replay](recorded-promotion-strata.md)

## Reproduce

Use the intact research archive and pinned GEPA dependency from the earlier replay.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -m benchmarks.recorded_promotion_coverage
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -m benchmarks.recorded_promotion_coverage \
  --execute PLAN_SHA256 --out result.json
```

The CLI validates the sealed archive before printing the new plan hash. The full result retains the holdout assignments, role coverage, qualification evidence, and paired outcomes. Two network-blocked runs produced byte-identical results.
