# Repairing merges with training counterexamples

The guarded merge study rejected all its candidates, including some whose component edits were structurally compatible. This follow-up checks whether measured training regressions can identify a local repair before validation. It uses the same four scripted fixture profiles and 16 new seeds for each profile. [Original merge comparison](component-merge.md)

CPO probes a proposed merge on up to four critical training cases. When a response identifies a broad component that violates a legacy case, the repair switches that component to its guarded form. A diagnosed interaction between two components vetoes the proposal. The repaired candidate must still preserve all measured validation passes from both parents and the current leader. It then receives complete validation. The holdout remains separate.

The primary arm reserves 12 validation lookups and up to four training lookups. Its matched reserve control spends the same allowance on ordinary search and attempts no merge. A veto-only arm uses the training evidence without changing components. The spare-budget arm starts with ordinary CPO and attempts training repair only if enough lookups remain to run both the probes and full validation. Each cost includes all distinct search lookups and scripted reflection slots.

## Recorded fixture results

Each cell gives exact holdout passes and charged calls over 64 fixture runs.

| Method | Cap 96 | Cap 144 |
| --- | ---: | ---: |
| Ordinary CPO | 1,767 / 5,812 | 1,932 / 7,674 |
| Original guarded merge | 1,733 / 5,321 | 1,836 / 7,258 |
| Matched reserve only | 1,733 / 5,194 | 1,796 / 7,104 |
| Training veto only | 1,733 / 5,226 | 1,796 / 7,138 |
| Reserved training repair | 1,799 / 5,372 | 1,863 / 7,259 |
| Spare-budget training repair | 1,767 / 5,812 | 1,948 / 7,700 |
| GEPA without merge | 1,534 / 5,737 | 1,834 / 7,381 |
| GEPA with native merge | 1,644 / 5,700 | 1,853 / 7,143 |

Reserved training repair accepted 10 merges across the two caps. It added 133 holdout passes and 333 calls over the matched reserve control, with no matched critical loss against that control. The gains were concentrated in legacy-heavy cases. At cap 96, it beat ordinary CPO on both legacy-heavy and component-interaction profiles under the cost and critical-preservation gate. Its legacy-heavy selections still lost critical cases passed by native GEPA.

The spare-budget arm found 41 candidate combinations and skipped 33 before buying any probes because a complete attempt could not fit. Its single accepted repair added 16 holdout passes over ordinary CPO at cap 144. The arm spent 26 additional calls at that cap. These are deterministic fixture results. The repair remains experimental. [Per-profile results and seal](component-merge-repair-results-v1.json)

A follow-up used the same training diagnostics earlier, during ordinary proposal generation. [Component feedback benchmark](component-feedback.md)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
PYTHONHASHSEED=0 python -m benchmarks.component_merge_repair
PYTHONHASHSEED=0 python -m benchmarks.component_merge_repair --execute PLAN_SHA256 --out result.json
```

The replay records whether each candidate was unfunded, vetoed, or accepted, together with its observed training and validation costs. [Runner](../benchmarks/component_merge_repair.py) · [Contract tests](../tests/test_component_merge_repair.py)
