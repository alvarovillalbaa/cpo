# Reserve room for a second independent proof

The exact-rejection retry rarely qualified a second nominee on MMLU. This replay tests whether the first proof leaves too few reads for a rival. It freezes the paid search and original nominee on all 2,240 archive episodes and compares two ways to divide the original 24-lookup proof cap. [Exact-rejection controls](witness-admission-retry.md) · [Runner](../benchmarks/witness_proof_split.py)

Both policies choose a rival from already-paid validation grades and fix its admission panel before reading any proof grades. They retire the original nominee's full base and allotted tie panels from the rival's pool. The rival needs at least nine reads to certify a one-win gain on eight rows, so the original nominee gets at most 15. If that first proof promotes, the episode ends. An exact rejection or an unfinished first proof sends any remaining allowance to the rival. Without an eligible rival and disjoint panel, the full single proof runs as before.

The futility arm ends the first proof earlier when its observed lower bound plus every possible favorable remaining grade falls below the gain requirement. The first allocation cannot reach a completed base tie on these panels. Both arms require the same exact promotion rule to deploy and retain the start if neither proof promotes. The replay compares the new arms with the full single proof and the previous 24-lookup retry. The other benchmark family selects a policy by promotion count within original seeded proof spend. The transfer requires a positive paired lower endpoint against the full single proof and realized spend within the original seeded control.

## Results

| Cohort | Full single proof passes / lookups | Exact-rejection retry passes / lookups | Reserved passes / lookups | Reserved with futility passes / lookups |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,301 / 74,526 | 17,037 / 76,006 | 17,121 / 75,764 |
| MMLU prior subjects | 21,180 / 34,122 | 21,180 / 35,226 | 21,153 / 35,943 | 21,174 / 35,910 |
| MMLU additional subjects | 8,976 / 13,639 | 8,973 / 14,339 | 8,984 / 14,779 | 8,989 / 14,759 |

The futility stop freed 1,844 first-proof reads relative to the fixed reservation. Rival proofs used 1,549 of those reads and earned 41 more promotions. Total spend fell by 295 lookups. On BBH and LMentry the paired 95% range against fixed reservation was +0.028 to +0.384 percentage points. Against retry after exact rejection it was −0.705 to −0.163 points.

On MMLU the reserved policies tried 459 rivals, up from 175 under exact-rejection retry. With futility, nine rivals promoted. The 15-read allocation lost 54 first-nominee promotions relative to full single proof. Pooled MMLU gained seven held-out passes at 2,908 extra lookups, and both subject-and-case intervals crossed zero. Both training families selected the full single proof. The attempted reservation exceeded the original seeded spend in all three cohorts and failed the transfer gate. [Full report and paired ranges](witness-proof-split-results-v1.json)

## Reproduce

Use a clean export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 20 targeted tests passed and two full replays matched byte for byte. The CLI rejected a stale seal, and the prospective development manifest reproduced byte for byte. The replay issued zero provider requests. Storage Guard measured 5.8 GiB free. The export, test overlay, and publication worktree used the standing 0.2 GiB LAB exception. [Budget and independence tests](../tests/unit/test_witness_proof_split.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_proof_split
python -B -m benchmarks.witness_proof_split \
  --execute 83973bd4db7868aa98fd3f7fa2a324f73bf35502e90ad785c1d8e44583fd56d9 \
  --out NEW_REPORT.json
```
