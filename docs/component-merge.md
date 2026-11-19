# Composing prompt components

`cpo.composition.merge_components(ancestor, left, right)` combines changes to named prompt components from a shared ancestor. It returns a new mapping when both parents contribute and their edits agree wherever they touch the same component. It returns `None` for conflicting edits or a result that duplicates a parent. Callers validate any returned candidate.

The benchmark gives CPO and official GEPA 0.1.4 the same scripted component editor and matched fixtures. Both can make up to six rounds of two reflection proposals. One GEPA arm enables its native merge configuration. CPO compares ordinary search, ordinary search with 12 validation lookups reserved, and reserved search followed by one optional merge.

The CPO merge requires two fully validated siblings with different successful validation cases and compatible component edits. It first checks whether the merge preserves the parents' and current leader's combined passes. A candidate that clears that check receives a complete validation before selection. One fixture adds a legacy case where individually compatible edits interact. The final holdout stays separate. Search costs count distinct evaluation lookups and scripted reflection slots. Mechanical merges incur no separate reflection charge.

## Results

Each cap covers 12 seeds and four deterministic profiles. Entries give exact holdout passes and charged search calls.

| Method | Cap 96 | Cap 144 |
| --- | ---: | ---: |
| Ordinary CPO | 1,367 / 4,417 | 1,486 / 5,698 |
| CPO with merge reserve | 1,342 / 3,971 | 1,419 / 5,447 |
| CPO with guarded merge | 1,342 / 4,001 | 1,419 / 5,494 |
| GEPA without merge | 1,224 / 4,277 | 1,344 / 5,468 |
| GEPA with native merge | 1,184 / 4,357 | 1,406 / 5,501 |

CPO rejected all 30 attempted merges. It selected the same prompts as the reserve-only control and spent 77 extra validation lookups across both caps. At cap 144 the guarded arm cleared both GEPA controls on the multi-clause and reverse-precedence profiles, where it attempted zero merges. GEPA accepted 44 merges across both caps. Native merge gained 62 holdout passes at cap 144 and lost 40 at cap 96 against GEPA without merging. The evidence supports a structural composition helper. The guarded search policy remains experimental. [Per-profile results and seal](component-merge-results-v1.json)

A follow-up repaired some candidate merges using measured training regressions before guarded validation. [Training-counterexample repair](component-merge-repair.md)

## Reproduce

The commands use the pinned GEPA package and a fixed Python hash seed.

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
PYTHONHASHSEED=0 python -m benchmarks.component_merge
PYTHONHASHSEED=0 python -m benchmarks.component_merge --execute PLAN_SHA256 --out result.json
```

The report records attempted merges, selected components, costs, critical comparisons, and search digests. [Composition helper](../cpo/composition.py) · [Benchmark runner](../benchmarks/component_merge.py) · [Contract tests](../tests/test_composition.py)
