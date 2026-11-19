# Ranking templates from other subjects

This replay gives CPO a template history gathered from formal logic, high-school computer science, and world religions. For each model, it evaluates the same 100 templates on four seeded cases per source subject and ranks challengers by their total passes. Only the two highest-ranked challengers advance to exact validation on the target subject. Source rows exclude the source holdouts. Target validation and holdout rows stay out of the profile.

The test uses 32 seeded candidate pools on each target panel and the same 171-lookup target cap for every arm. All CPO variants in the matched shortlist comparison use the same adaptive rejection and exact validation. The cold controls take the first two challengers or choose two from target training probes. The two history-ranked GEPA controls have access to the same source scores. The original GEPA controls keep their seeded proposal order. [PromptEval data and protocol](prompteval-transfer.md) · [Adaptive rejection](prompteval-rejection.md)

## Results

The eight transfer panels reuse recorded subjects from the second-model screen. The prior and target subjects are disjoint in both phases. Gathering the four-case history costs 1,200 source lookups per model, paid once across that model's target panels. The eight-case variant doubles the profile cost. The target-only counts show the cost when the profile has already been collected.

| Method | Transfer holdout passes | Target lookups | Source lookups | Total lookups |
| --- | ---: | ---: | ---: | ---: |
| CPO, first two in seeded order | 10,271 | 13,628 | 0 | 13,628 |
| CPO, two from target training | 10,272 | 19,859 | 0 | 19,859 |
| CPO, four-case source profile | 10,244 | 13,668 | 2,400 | 16,068 |
| CPO, eight-case source profile | 10,243 | 13,688 | 4,800 | 18,488 |
| CPO, source profile and target rerank | 10,236 | 15,666 | 2,400 | 18,066 |
| Sequential GEPA | 10,264 | 21,276 | 0 | 21,276 |
| Batched GEPA | 10,284 | 20,808 | 0 | 20,808 |
| Sequential GEPA, source ranked | 10,283 | 20,694 | 2,400 | 23,094 |
| Batched GEPA, source ranked | 10,269 | 20,982 | 2,400 | 23,382 |

The four-case profile cleared both original GEPA gates on two of eight panels and all four GEPA gates on one. Across the eight panels it lost 27 passes and spent 2,440 more lookups than taking the first two challengers in seeded order. The 40-lookup deficit remains when the source profile is already available. It also lost 14 holdout passes against the seeded control on the four development panels. More source observations and a local training rerank did not recover these gaps. Cross-subject history remains experimental. [Frozen plans, accounting, and panel results](prompteval-subject-history-results-v1.json)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.prompteval_subject_history --phase retrospective-transfer
python -m benchmarks.prompteval_subject_history --phase retrospective-transfer --execute PLAN_SHA256 --out result.json
```

Use `--phase development` for high-school statistics and European history. The result includes separate source and target counts, source observation digests, and every split's selected template and search digest. [Runner](../benchmarks/prompteval_subject_history.py) · [Accounting tests](../tests/test_prompteval_subject_history.py)
