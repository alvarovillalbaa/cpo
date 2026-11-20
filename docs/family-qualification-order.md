# Order fresh qualification replies by expected proof cost

Late miss substitution failed its frozen transfer. This replay keeps search fixed and measures whether qualification needs fewer evaluations to reach the same decision. The existing paired certificate stops when unread outcomes can no longer change promotion. The new policy changes which qualification reply it reads next. [Late miss transfer](late-miss-transfer.md) · [Existing paired certificate](paired-qualification.md)

The benchmark uses exact binary qualification with one or two case groups. A strict net gain is required, and no group may lose passes. For each prompt, the pass-rate estimate comes from its already observed validation replies, adds one success and one failure, and rounds to the nearest quarter among 1/4, 1/2, and 3/4. The scheduler treats replies as independent under these fixed estimates. A finite-state calculation chooses the next group and prompt that minimize expected remaining lookups under that model. Only actual qualification replies update the lower and upper bounds and determine the result. Wider, repeated, or critical-case panels retain the original certificate. [Runner](../benchmarks/family_qualification_order.py)

The comparison applies the same scheduler to fresh qualification for the original CPO route and both official cap-52 GEPA controls. Archive preflight and its search debit stay fixed. Each of the 44 panels runs the original 32 four-cycle episodes. The replay must reproduce published scores and costs before the change. It then checks every deployment and search journal against its exact original counterpart. [Source panels](late-miss-transfer.md) · [Earlier qualification ordering](prompt-paired-reply-order.md)

## Results

The scheduler preserved all 16,896 cycle deployments and search traces across the three methods. CPO saved 1,430 lookups, or 4.4% of its qualification lookups and 1.1% of all its lookups. Both GEPA controls also saved lookups. [Per-panel results and design seal](family-qualification-order-results-v1.json) · [Verification receipt](family-qualification-order-verification-v1.json)

| Method | Original qualification | Ordered qualification | Lookups saved |
| --- | ---: | ---: | ---: |
| CPO | 32,273 | 30,843 | 1,430 |
| Batched GEPA | 16,690 | 15,701 | 989 |
| Sequential GEPA | 25,867 | 24,232 | 1,635 |

CPO used 130,377 lookups overall, down from 131,807. On the Mixtral–Falcon cohort, sequential GEPA still finished with 29,625 total holdout passes against CPO’s 29,616. These are fixed-archive results. The fresh-model comparison remains pending.

## Use the scheduler

```python
from cpo.expected_qualification import certify_expected_qualification

decision = certify_expected_qualification(
    incumbent,
    challenger,
    qualification_rows,
    evaluate,
    validation_counts=((4, 6), (6, 8)),
)
```

`evaluate(prompt, row, repeat)` returns an exact boolean. Supply earlier validation counts as `(passed, observed)` for the incumbent and challenger in that order. With no counts, both pass-rate estimates default to one half. The scheduler handles up to eight qualification rows in one or two families. If an evaluation cap interrupts the proof, the return value carries the incumbent and an `undecided` status. [Package implementation](../cpo/expected_qualification.py)

For a supplied prompt pool, the public fixed-pool cycle collects validation counts and applies the scheduler in one call. [Expected-cost cycle](expected-cost-cycle.md)

## Reproduce offline

Use pinned GEPA 0.1.4. Preview the frozen inputs to obtain the design seal, then run with that seal and a new output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.family_qualification_order
PYTHONHASHSEED=0 python -B -m benchmarks.family_qualification_order \
  --execute DESIGN_SHA256 --out NEW_REPORT.json
```

Two runs from a clean source export reproduced the same report with sockets and DNS disabled. The focused tests exhaust all 256 assignments of binary outcomes on a four-row, two-family panel and cover capped and repeated qualification. The built wheel was installed into a temporary directory and exercised outside the source tree. [Tests](../tests/unit/test_family_qualification_order.py) · [Verification receipt](family-qualification-order-verification-v1.json)
