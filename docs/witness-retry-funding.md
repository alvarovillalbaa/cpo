# Fund a retry after the full first proof settles

Moving reads between two proofs and changing the second proof's order failed to transfer. This replay keeps the full first proof and all its promotions. Only an exact rejection can open a retry, using the original paid rival and independent panel. The joint cap remains 24 lookups. [Proof order result](witness-same-case-order.md) · [Original exact-rejection retry](witness-admission-retry.md) · [Runner](../benchmarks/witness_retry_funding.py)

Five gates screen retries using only information known at that point. Two require at least 12 or 14 reads left. One requires a positive net gain on shared paid validation cases against the start. Another requires a higher smoothed validation pass rate, using one prior pass and one prior failure per prompt. The final gate combines the smoothed gain and the 12-read threshold. Skipping a retry keeps the start and spends only the completed first proof.

The comparison freezes the paid search and checks the original seeded proof, full expected-read proof, and unfiltered exact-rejection retry. The other benchmark family selects a gate by exact promotions within original seeded spend. Lower proof spend breaks ties. The transfer gate requires a positive paired lower endpoint against the full expected-read proof and realized spend no greater than the seeded proof in every cohort.

## Results

| Held-out cohort | Gate selected outside family | Full first proof passes / lookups | Selected gate passes / lookups | Unfiltered retry passes / lookups | Paired 95% range vs full first proof, percentage points |
| --- | --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | At least 14 reads left | 17,068 / 71,071 | 17,253 / 71,868 | 17,301 / 74,526 | +0.239 to +0.639 |
| MMLU prior subjects | At least 12 reads left | 21,180 / 34,122 | 21,180 / 34,398 | 21,180 / 35,226 | −0.013 to +0.013 |
| MMLU additional subjects | At least 12 reads left | 8,976 / 13,639 | 8,973 / 13,812 | 8,973 / 14,339 | −0.070 to +0.016 |

The rule fitted on MMLU passed on BBH and LMentry. It gained 185 held-out passes, kept 30 of the unfiltered retry's 42 promotions, and spent 666 fewer lookups than the original seeded proof. BBH and LMentry selected the 12-read rule, which retained both MMLU retry promotions and saved 1,355 lookups against the unfiltered retry. It still exceeded the MMLU seeded proof allowance by 113 lookups and yielded three fewer MMLU passes than the single proof. The full cross-family gate failed. [All five gates and fit statistics](witness-retry-funding-results-v1.json)

Five settings in the published BBH and LMentry native GEPA sweep fit the selected rule's 71,868-lookup budget. The strongest observed setting was batched GEPA with 12 validation rows and cap 44. It recorded 16,180 held-out passes on the same episodes at 71,655 lookups, a difference of 1,073 passes. The paired intervals above compare against CPO's full first proof. [Published native sweep](witness-cached-gepa-evidence-results-v1.json)

## Reproduce

Use a clean source export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 42 targeted tests passed and two full replays matched byte for byte. Original control costs and scores reproduced, the CLI rejected a stale seal, and the prospective live manifest reproduced byte for byte. Storage Guard measured 5.9 GiB free. The source export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Funding gate tests](../tests/unit/test_witness_retry_funding.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_retry_funding
python -B -m benchmarks.witness_retry_funding \
  --execute 855637012a2b20b62eaae1a17cce8d171203642a4457c06897746e860e481107 \
  --out NEW_REPORT.json
```
