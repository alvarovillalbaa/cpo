# Development gate with unknown grades

`assess_development_bounds` evaluates the paired development gate when some physical replies have no exact grade. Pass `None` for a reply that reached its output cap, and omit the tail for requests that have yet to return. Arms that share a physical request always share its outcome. [Implementation](../cpo/development_qualification_bounds.py)

```python
from cpo.development_qualification_bounds import assess_development_bounds

decision = assess_development_bounds(
    schedule, observations, gate=development_gate, search_costs=measured_search_costs
)
```

`impossible` means every assignment of pass or fail to the unknown grades fails the gate. `guaranteed` means every assignment passes. `undetermined` means the verdict depends on unknown outcomes. One favorable and one unfavorable assignment suffice. A sample shared with CPO affects its task total, and its effect cancels in any comparison with a control sharing that sample. The assessed verdict applies to the supplied schedule and search costs. The study protocol still governs dispatch, retries, and promotion.

## Recorded GPT-6 Luna v1 outcome

Eight of 216 physical qualification replies reached their output cap. All eight were outage replies for GEPA controls. The original CPO 0.2.0 nominee received 36 complete answers per task and scored zero exact passes on each. For the original selected prompts, treating the eight capped outcomes as unknown leaves the development gate impossible. Each GEPA control already had one confirmed outage pass. The ticket task became unreachable at reply 10, when CPO could at best reach 26 of the required 27 passes. The first cap occurred at reply 108. [Bounded replay receipt](typed-development-cap-bounds-results-v1.json) · [Original replay](typed-development-futility.md)

The audit verified the original archive fingerprints and reran the sealed qualification decision before changing any analysis grades. It keeps the original request order and measured costs. The 206 replies after the cutoff account for $0.274521 in recorded usage at plan rates. That suffix was executed in the original trial. The analysis cannot determine whether different search replies would have changed the selected prompts. [Audit](../benchmarks/typed_development_cap_bounds.py)

```sh
python -B -m benchmarks.typed_development_cap_bounds \
  --archive PATH_TO_LIVE_CPO_V1/qualification --out NEW_REPORT.json
```

Eleven focused tests passed. They included exhaustive assignments for partially observed panels with shared samples, repeated cases, critical regressions, and both the quality and cost gates. The archived report reproduced byte for byte. No provider requests were sent. [Tests](../tests/unit/test_development_qualification_bounds.py)
