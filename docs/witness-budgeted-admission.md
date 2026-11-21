# Choose proof reads under the remaining admission allowance

The matched validation probe left some independent proofs unfinished. This follow-up keeps the CPO nominee, validation grades, and admission cases fixed. It compares three ways to order the proof at the same 16-, 20-, and 24-lookup allowances. [Probe results](witness-nominee-probe.md) · [Runner](../benchmarks/witness_budgeted_admission.py)

Seeded order follows the published proof's row sequence. Expected-read order plans for a complete proof and chooses the side with the lowest expected remaining work. Budget lookahead maximizes the modeled chance of certifying promotion before the cap. It then favors settling the decision and finally minimizing expected reads. Both planners start from the same pooled paid validation rate, update estimates with actual proof grades, and account for the reserve available after a base tie. The estimates choose read order. Exact observed score bounds decide admission. [Scalar proof implementation](../cpo/halving/qualification_budget.py)

The comparison checks every episode against the complete seeded proof. Each planner must reproduce its decision at the full allowance. An unfinished proof keeps the start at a tighter allowance. Admission outcomes from the other benchmark family choose an order and cap based on promotions at no more than the original proof spend. The transfer gate tests realized lookup cost and a positive paired lower endpoint against full seeded proof on each held-out cohort.

## Results

Both training families selected expected-read ordering with the full allowance. It reproduced all deployed prompts and their holdout passes while saving 1,799 paid lookups. Budget lookahead also reproduced these deployments and saved 886. [Complete same-cap results and paired intervals](witness-budgeted-admission-results-v1.json)

| Cohort at cap 24 | Holdout passes | Seeded paid lookups | Expected-read order | Budget lookahead |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 | 72,534 | 71,071 | 71,829 |
| MMLU prior subjects | 21,180 | 34,343 | 34,122 | 34,224 |
| MMLU additional subjects | 8,976 | 13,754 | 13,639 | 13,692 |

At cap 20, each planner recorded 50 more rejections than seeded order across the three cohorts. Promotion counts and holdout scores stayed the same at that cap. The paired score ranges were zero at every matched cap. The quality transfer gate remains unmet. The efficiency result applies to fixed archived grades, and fresh provider behavior remains unverified.

An independent retry after exact rejection improved the BBH and LMentry cohort within the original spend, but failed to transfer to either MMLU cohort. [Independent retry replay](witness-admission-retry.md)

The opt-in function supports short, noncritical scalar panels from one family. Use `prioritize_promotion=False` for the expected-read policy.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel from a clean source export. Fifteen targeted tests passed with sockets and DNS blocked. The exhaustive checks cover all 4,096 boards of three base and three reserve cases under both planners and three caps. The cap-24 totals reproduced in a second replay, the CLI rejected a stale seal, and the original live plan reproduced byte for byte. Storage Guard measured 5.8 GiB free. The temporary export and overlay fit the standing 0.2 GiB LAB exception and were removed. [Boundary and parity tests](../tests/unit/test_qualification_budget.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_budgeted_admission
python -B -m benchmarks.witness_budgeted_admission \
  --execute 0a8b2db7a8812950fb597a03697f5501c480687c2e3074901a364bb1d87cbd44 \
  --out NEW_REPORT.json
```
