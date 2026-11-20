# Run the opening screen with a supplied proposal pair

Use the opt-in `run_opening_screen_cycle` API when a rewrite and a repair are already available. The cycle screens the pair with the normal CPO search, using the first eight validation rows by default. It reserves enough of the search budget to complete validation for the incumbent and the finalist. [Package API](../cpo/opening_screen_cycle.py) · [30-panel transfer benchmark](proposal-opening-transfer.md)

```python
from cpo import ProposalPair
from cpo.opening_screen_cycle import run_opening_screen_cycle

result = run_opening_screen_cycle(
    incumbent,
    training_rows,
    validation_rows,
    qualification_rows,
    evaluate,
    opening_pair=ProposalPair(rewrite, repair),
    metric_limit=72,
    qualify=qualify,
    screen_rows=8,
)

next_incumbent = result.prompt
paid_lookups = result.search.evaluations + result.qualification_evaluations
```

Supply nonempty training, validation, and qualification cohorts with disjoint row IDs. The training cohort records the data reserved for generating the opening. The cycle evaluates validation and qualification rows. `evaluate(prompt, row)` returns an `Observation` with an exact boolean pass, and `qualify(prompt, row, repeat)` returns a boolean. The search budget must cover at least two complete validation passes. If the panel has fewer than `screen_rows` rows, search uses the whole panel.

A finalist advances only with a strict total gain across full validation, preserved incumbent passes on critical rows, and nonnegative gain in each validation family. Setting `field_credit=True` lets the short screen use matched-field counts. Full validation and qualification still require exact passes. The independent gate supports repeated responses, critical rows, and a separate `qualification_limit`. An undecided qualification retains the incumbent. With a qualification cap below a complete paired panel, `certify_opening=True` can skip incumbent reads after a perfect rewrite. The expected-cost schedule uses complete validation totals. `result.search.events` records a full validation decision or a `certified-full-validation` decision. [Qualification certificate](paired-qualification.md) · [Opening certificate](opening-certificate.md)

## Verification

The exported source and a separately installed wheel reproduced all 30 published panel traces across 3,840 cycles. They matched validation requests, independent qualification requests, deployed prompts, lookup charges, and holdout scores. Twelve focused tests passed in each environment. The tests cover the full validation reserve, disjoint cohorts, critical and family regressions, typed field observations, and a zero qualification allowance.

On the recorded transfer panels the screen used 50.9% fewer evaluation lookups than batched GEPA and finished seven passes ahead. The joint paired 95% range was −91 to +90 passes. The replay measures archived evaluation and qualification. Live proposal quality and generation cost remain unmeasured. [Replay artifact](opening-screen-api-replay-v1.json) · [Verification receipt](opening-screen-api-verification-v1.json)

The typed fixture comparison found that later reflection recovered fields missed by the supplied opening. [Typed benchmark](opening-screen-typed.md)

Use the [opening-repair cycle](opening-repair-cycle.md) to fund one later proposal after an incomplete opening.

## Reproduce offline

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_screen_api_replay
PYTHONHASHSEED=0 python -B -m benchmarks.opening_screen_api_replay \
  --execute 69368267e4395eb65ecd1178e8d5ce29bb6b240992feebad8440aef435684855 \
  --out NEW_REPORT.json
```

Both verification runs blocked sockets and DNS. The wheel build and installation used local tooling with the package index disabled. The two replay files matched byte for byte. The CLI rejected a stale seal and preserved an existing result. Storage Guard measured 4.5 GiB free. The 26.9 MB export, build, and install directory was removed under the standing LAB exception. [Replay runner](../benchmarks/opening_screen_api_replay.py) · [Focused tests](../tests/unit/test_opening_screen_cycle.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
