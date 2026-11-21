# Share one lookup allowance across both admission routes

Direct admission after a stalled search and selective retry after a rejected proof both improved archived BBH and LMentry results relative to the single-proof policy. Their combined spend can exceed the saved lookups. This replay shares one batch allowance between them while preserving the paid search and every first proof. A stalled search offers its supported-rate candidate. An exact rejection offers its original paid rival only when the existing 14-read gate on BBH and LMentry or 12-read gate on MMLU allows it. [Direct admission budget](witness-admission-credit.md) · [Selective retry](witness-retry-funding.md) · [Runner](../benchmarks/witness_shared_admission_credit.py)

The cohort allowance is assigned from the published seeded-to-expected proof savings before the replay. A direct proof reserves 24 lookups. A retry reserves the unused part of the first proof's 24-lookup episode cap and uses its own independent panel. The queue skips offers that cannot be funded, settles each exact proof, and returns unused reads before considering the next offer.

The controls fund either route by itself at the same allowance. The shared policies process direct offers first, retry offers first, or both in scheduled episode order. These orders are fixed before optional proof replies. The other family selects using promotion counts and then charged lookups. To qualify, the selected order needs a positive paired held-out lower endpoint and must stay within seeded spend in all three cohorts.

## Results

| Cohort | Full single proof passes / lookups | Direct only | Retry only | Direct first | Retry first | Scheduled order |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,146 / 72,121 | 17,253 / 71,868 | 17,203 / 72,523 | 17,290 / 72,530 | 17,209 / 72,526 |
| MMLU prior subjects | 21,180 / 34,122 | 21,190 / 34,323 | 21,180 / 34,333 | 21,190 / 34,336 | 21,180 / 34,333 | 21,189 / 34,332 |
| MMLU additional subjects | 8,976 / 13,639 | 8,976 / 13,692 | 8,976 / 13,753 | 8,976 / 13,753 | 8,976 / 13,753 | 8,976 / 13,753 |

On BBH and LMentry, the best observed shared order tried retries first. It funded 66 retries and 51 direct proofs, with 43 promotions. It added 222 held-out passes over the single proof and stayed four lookups below the seeded budget. It added 37 passes over retry alone for 662 additional lookups.

The outside-family selection picked direct-only for BBH and LMentry, with a paired 95% range of +0.057 to +0.327 percentage points. It picked retry-first for both MMLU cohorts. That order spent 325 lookups on MMLU and promoted no candidate, so both paired ranges were exactly zero. The shared queue met every cost cap and failed the all-cohort quality gate. [Full results and route-level receipts](witness-shared-admission-credit-results-v1.json)

## Reproduce

Use a clean export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 58 targeted tests passed and two full replays matched byte for byte. The standalone direct queue, the complete unbudgeted retry offers, and the original proofs reproduced their published scores and costs. The CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 6.4 GiB free. The export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Budget tests](../tests/unit/test_witness_shared_admission_credit.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_shared_admission_credit
python -B -m benchmarks.witness_shared_admission_credit \
  --execute 93255d97f8d5661cdeede912ef9aae621f5c2cde2e98f945e2847bfb551b6595 \
  --out NEW_REPORT.json
```
