# Price the nomination and qualification gap in archived CPO episodes

The two rejected-finalist searches cost more across the archived cohorts. This audit asks how much room remains in three decisions across the same 64 Promptolution episodes. It verifies the original scores, cycle decisions, and paid traces, then advances each possible trajectory from the incumbent that would actually have entered the next cycle. [Rejected-finalist searches](feedback-rejection-scout.md) · [Benchmark](../benchmarks/promptolution_stage_headroom.py)

1. A **promotion veto** can keep the incumbent after the packaged screen and independent qualification have been paid. It keeps the observed feedback signal.
2. **Known nomination** can also start from any one enrolled challenger in a cycle the policy would search. It pays for a strict validation certificate over the original panel and the existing independent qualification. Hindsight identifies the challenger at zero discovery cost.
3. The **qualification bound** also permits deploying a finalist that failed the paid independent proof. It keeps the observed rejection signal and the same charges. This is a retrospective estimate of what the proof excluded.

The solver keeps the cheapest arrival at each incumbent and feedback state. It scores final prompts against the original holdout and computes the best combination at either the original per-episode caps or one pooled cap. The nested menus measure reachable score under these particular search and proof prices. Their decisions use hindsight.

## Pooled score and lookup cost

| Choice | Settled passes / lookups | Feedback passes / lookups |
| --- | ---: | ---: |
| Packaged | 3,924 / 2,455 | 3,885 / 2,348 |
| Promotion veto | 3,934 / 2,455 | 3,889 / 2,346 |
| Known nomination, independent proof required | 4,177 / 2,447 | 4,163 / 2,345 |
| Qualification bound | 4,306 / 2,443 | 4,300 / 2,347 |

At each episode's own cap, known nomination reaches 4,006 passes for settled and 3,961 for feedback. The settled veto gains six at those caps, versus ten with pooled spending. The larger gain from known nomination therefore persists with the original budgets held episode by episode. [Results by task, capped costs, and attaining-path hashes](promptolution-stage-headroom-v1.json)

The broader archived controls reach **4,141 passes in 1,757 lookups** with per-episode hindsight. Matching that score while keeping qualification requires at least 2,338 lookups for settled and 2,292 for feedback in the known-nomination menu. The qualification bound needs at least 2,120 and 2,073, respectively. Even when hindsight supplies the nominee, the tested paths need more lookups to match that score. Candidate ordering and the cost of search and proof both matter. The packaged policies continue to require independent qualification. Live superiority remains unverified. [Matched control menu](promptolution-settled-episode-headroom.md)

## Reproduce offline

Use the frozen Promptolution corpus and GEPA 0.1.4 environment from the original transfer.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.promptolution_stage_headroom \
  --corpus PREDICTIONS.json \
  --execute 7884629e674a36c770b320bea1b117638233bf51a7bad58452b3beba3b721613 \
  --out /tmp/promptolution-stage-headroom.json
```

Two network-disabled replays produced byte-identical receipts. All 94 focused tests passed, including the paid veto, the distinct feedback states, and the minimum-cost attainer. Storage Guard measured 9.9 GiB free. The disposable source, pinned wheel overlay, corpus copy and publication checkout fit the standing 0.2 GiB LAB exception. Teardown was verified. [Tests](../tests/unit/test_promptolution_stage_headroom.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
