# Reusing paid prompt evaluations across cycles

The weighted two-row screen missed an available exact validation improvement on 110 of 148 exploratory splits where a better candidate existed. More validation probes recovered some improvements. They also increased costs, and choosing the exact validation winner from the entire pool would have gained only two aggregate holdout passes on those six panels. This motivated a separate test of evidence from earlier cycles. [Weighted screen](prompteval-witnesses.md)

Each arm begins with an empty observation cache and pays for a candidate-case lookup the first time it requests it. All arms get the same 32 candidate pools, incumbent choices, search splits, and per-cycle cap of 171 distinct requests, including cache hits. Nothing carries across model or subject boundaries. A fixed 30% subject holdout stays outside the cache and is scored after each cycle.

CPO's history variants collect the ordinary two training probes and rank candidates by smoothed correctness from the probes and outcomes already paid for. They exclude prior outcomes on the current validation rows from the ranking. The incumbent keeps its place unless an exact validation challenge achieves a strict improvement. The primary variant challenges at most one prompt, and a secondary variant allows two. GEPA runs with cache access in both proposal-order controls and with the same history estimate ordering its proposals in the other two controls. The original GEPA paths and the original minibatch paths reproduce their previously recorded selections and requests.

## Results

Entries are aggregate holdout passes and newly paid search lookups. The European history and statistics panels were examined in an earlier study and serve here as a retrospective recheck.

| Phase | One-challenger CPO | Two-challenger CPO | Original CPO with cache | Sequential GEPA with cache | Batched GEPA with cache | Sequential GEPA with history | Batched GEPA with history |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Six exploratory panels | 4,468 / 10,791 | 4,477 / 12,415 | 4,461 / 9,303 | 4,475 / 13,097 | 4,464 / 12,933 | 4,451 / 12,887 | 4,489 / 12,823 |
| Four recheck panels | 4,120 / 7,459 | 4,133 / 8,284 | 4,106 / 6,281 | 4,138 / 10,026 | 4,138 / 9,603 | 4,150 / 9,862 | 4,139 / 9,586 |

One-challenger CPO cleared the documented gate against all four GEPA controls on two of six exploratory panels and two of four recheck panels. On recheck, it used about 26% fewer paid lookups than sequential GEPA with caching and fell 18 passes short. The two-challenger variant narrowed that gap to five passes at 17% fewer paid lookups. Reuse helped on both European-history panels, while both statistics panels still fell short. The comparison measures a repeated workload with recurring prompts and cases. Performance with fresh provider replies and a cache that rarely hits remains unmeasured. [Panel decisions and seals](prompteval-history-results.json)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.prompteval_history --phase recheck
python -m benchmarks.prompteval_history --phase recheck --execute PLAN_SHA256 --out result.json
```

Use `--phase exploratory` to replay the original six panels. The runner emits split-level choices, cache hits, paid lookup counts, and digests of the observations requested. [Runner](../benchmarks/prompteval_history.py) · [Accounting tests](../tests/test_prompteval_history.py)
