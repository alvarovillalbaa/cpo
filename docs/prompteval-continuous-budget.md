# Early stopping and incumbent-dependent budgets

This experiment follows the four-cycle replay, where CPO's final prompts scored slightly higher than GEPA's at nearly double the lookup cost. Each experimental CPO arm uses the same ordered proposal blocks and disjoint paired qualification. The search budget applies to each cycle and the reported cost includes both sides of all qualification pairs. [Original four-cycle comparison](prompteval-continuous.md)

The rank-only arm keeps the highest-ranked parent and prunes a candidate when even its optimistic validation score cannot overtake the leader. Three other arms stop after gaining two exact validation passes over the incumbent or after two rounds without an increase in the leader's exact score. They use search caps of 171, 96, and 112. The primary policy uses the same stopping and pruning rules and chooses a cap from the incumbent's paid validation results. It spends up to 64 lookups when the incumbent passes at least 18 of 24 validation rows and up to 112 otherwise. Those incumbent lookups are reused within search.

## Recorded results

The development sweep informed the primary policy. It was frozen before running these configurations on the eight previously studied transfer panels. Each cell gives final held-out passes and charged search plus qualification lookups.

| Method | Four development panels | Eight transfer panels |
| --- | ---: | ---: |
| Original CPO cycle | 4,192 / 87,304 | 10,270 / 174,349 |
| Rank-only CPO | 4,206 / 86,316 | 10,277 / 172,649 |
| Early stopping, cap 171 | 4,194 / 52,212 | 10,218 / 107,953 |
| Early stopping, cap 96 | 4,157 / 43,946 | 10,208 / 89,457 |
| Early stopping, cap 112 | 4,176 / 47,196 | 10,210 / 97,497 |
| Early stopping, incumbent-dependent cap | 4,177 / 43,269 | 10,214 / 88,935 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 |

The incumbent-dependent policy cleared both GEPA comparisons on two development panels and zero transfer panels. Across all eight transfer panels it saved about 49% of the original CPO cycle's lookups and lost 56 held-out passes. It spent 709 more lookups than batched GEPA and lost 49 passes. Rank-only CPO gained seven passes and saved 1,700 lookups against the original CPO cycle on transfer, with lookup cost still close to twice that of batched GEPA.

The evaluation uses recorded correctness with the same supplied candidate stream. The prototype is archived as an optional research patch. [Seals and panel results](prompteval-continuous-budget-results-v1.json)

## Reproduce

From a disposable checkout at the report commit, install the benchmark dependencies and apply the prototype patch.

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
git apply --unidiff-zero benchmarks/patches/continuous-budget-policy.patch
python -m benchmarks.prompteval_continuous_budget --phase retrospective-transfer
python -m benchmarks.prompteval_continuous_budget --phase retrospective-transfer --execute PLAN_SHA256 --out result.json
```

Use `--phase development` for the original four panels. Each report includes the selected cap, paid incumbent score when used, qualification receipts, and final selection for every run. [Benchmark runner](../benchmarks/prompteval_continuous_budget.py) · [Prototype](../benchmarks/patches/continuous-budget-policy.patch) · [Budget test](../tests/test_prompteval_continuous_budget.py)
