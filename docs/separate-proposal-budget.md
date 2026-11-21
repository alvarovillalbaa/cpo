# Cap paid proposals separately from evaluations

`SequentialSearchBudget` accepts `proposal_limit` in the same charge units as the overall search limit. Sequential selection reserves the full quote for the next proposal against the unused proposal allowance. Batched selection reserves every proposal in the batch before entering it. Both settle actual proposal charges. Supplied proposals can use a zero quote and charge. The overall limit still covers all search charges. [Sequential selector](../cpo/sequential_field_rewrite.py) · [Batched selector](../cpo/batched_field_rewrite.py)

```python
from cpo.sequential_field_rewrite import SequentialSearchBudget

budget = SequentialSearchBudget(
    limit=search_allowance,
    evaluation_quote=maximum_evaluation_charge,
    proposal_quote=quote_proposal,
    observed_proposal=settle_proposal,
    proposal_limit=reflection_allowance,
)
```

The optional limit controls spending, which can change which proposals enter search. In a replay of 240 retained Sol paths at each of five tariffs, a one-quote limit produced the same CPO charges and held-out outcomes as the shared budget. Excluding paid later reflections preserved all matched outcomes and moved the widest-ceiling savings at the two lowest price ratios from 3.45% and 8.19% to 16.60% and 16.40%.

The feedback-driven fixture exposed the quality trade-off. At its lowest reflection price, a shared or one-quote budget passed 619 of 648 held-out cases and cost 1,924 charge units. Excluding paid later reflections passed 593 and cost 1,802. These replay results support keeping the default shared search budget and choosing a separate cap when the application has a firm proposal allowance. Live quality at any cap remains unverified. [Feedback benchmark](recorded-paired-field-rewrite.md#skip-reflections-when-the-parent-minibatch-passes)

The tests cover exact-boundary reservations, zero-quoted supplied proposals, reuse of unused reservation after settlement, invalid limits, and the full quote for a batched round. [Sequential tests](../tests/unit/test_sequential_field_rewrite.py) · [Batched tests](../tests/unit/test_batched_field_rewrite.py)
