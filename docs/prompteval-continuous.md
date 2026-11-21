# Four consecutive optimization cycles

This replay compares how CPO and GEPA improve a prompt over four cycles. Every arm starts from the same template and sees the same four blocks of 12 distinct alternative templates in the same seeded order. The templates come from recorded PromptEval matrices. An arm carries its own incumbent into the next cycle. [Source data and single-cycle protocol](prompteval-transfer.md)

Each cycle has a search cap of 171 lookups, 12 training cases, and 24 validation cases. Training and validation can reuse cases across cycles. A proposed replacement must gain at least one exact pass on that cycle's eight paired qualification cases. The 32 qualification cases per episode are disjoint from the search cases and from the final holdout. A tied or worse qualification keeps the incumbent. Final holdout cases are scored after all four cycles. Both sides of every qualification pair are charged.

The primary CPO arm uses the public `run_cycle` API with a precomputed opening pair and the finite proposal queue. The pool variants use adaptive rejection on two or four challengers. The margin variant checks two training cases only when the selected challenger leads the incumbent by one validation pass and vetoes it if the challenger loses that training comparison. Both official GEPA 0.1.4 controls use the same paired qualification and incumbency rules as CPO.

## Recorded results

Each cell gives final holdout passes and total search and qualification lookups across 32 four-cycle episodes per panel. The four development and eight transfer panels reuse earlier recorded subjects. The final holdout rows repeat across episodes within a subject.

| Method | Four development panels | Eight transfer panels |
| --- | ---: | ---: |
| Starting prompts | 4,124 / 0 | 10,224 / 0 |
| CPO cycle | 4,192 / 87,304 | 10,270 / 174,349 |
| CPO pool, two challengers | 4,171 / 30,827 | 10,199 / 63,332 |
| CPO pool, four challengers | 4,181 / 43,180 | 10,190 / 88,938 |
| CPO pool, four with margin check | 4,178 / 43,637 | 10,186 / 89,725 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 |

On the transfer panels, the primary CPO cycle made 211 promotions and gained 46 final holdout passes over the starting prompts. Batched GEPA made 93 promotions and gained 39 passes. CPO finished seven passes ahead at nearly twice the lookup cost. The two-challenger pool reduced lookup count by 28% against batched GEPA and finished 64 passes behind. It cleared both controls on one of eight transfer panels. The four-challenger pool and the margin check cleared both controls on two of four development panels and zero of eight transfer panels. The primary CPO cycle missed the combined cost and quality gate on every panel.

The replay tests how candidate search and qualification interact over repeated cycles with a supplied proposal stream. New prompt generation, additional tasks, and live provider costs remain unmeasured. [Seals and panel results](prompteval-continuous-results-v1.json)

The follow-up used incumbent validation to choose a lower search cap. It nearly halved CPO's costs and fell short of batched GEPA on the transfer panels. [Early stopping and budget results](prompteval-continuous-budget.md)

A separate replay qualified earlier contenders on each cycle's fresh cases before paying for search. It saved CPO lookups and still missed the gate against GEPA with the same option. [Archive qualification replay](prompteval-archive-cycles.md)

The proposal-cycle API follow-up used an exact qualification early stop and reproduced the search and deployment at five caps. [Expected-cost proposal cycle](expected-cost-proposal-cycle.md)

A matched replay gave all three optimizers the same search ceiling, split-safe case IDs, and the option to return unread qualification cases to later cycles. Recycling produced mixed gains and kept CPO behind the wider GEPA controls on the pooled quality and cost comparison. [Qualification case reuse](prompteval-qualification-case-reuse.md)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.prompteval_continuous --phase retrospective-transfer
python -m benchmarks.prompteval_continuous --phase retrospective-transfer --execute PLAN_SHA256 --out result.json
```

Use `--phase development` for the four development panels. The report records every incumbent transition, paired qualification outcome, lookup count, and search digest. [Runner](../benchmarks/prompteval_continuous.py) · [Contract tests](../tests/test_prompteval_continuous.py)
