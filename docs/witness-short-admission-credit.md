# Shorten optional proofs to fit the lookup balance

The adaptive queue treated a full proof quote as the price of entry. This replay keeps the same original search, optional proof offers, independent panels, and batch allowances. It tests whether a shorter reservation can fund more attempts. The queue still chooses routes using earlier settled promotions and paid reads. [Adaptive queue](witness-adaptive-admission-credit.md) · [Runner](../benchmarks/witness_short_admission_credit.py)

The base-cap policy reserves at most the cost of reading both sides of the base panel, or the original quote if smaller. It can certify a base gain. A base tie normally needs extra reads and stays undecided when those reads fall outside the cap. The balance-cap policy requests the full quote while it fits and otherwise reserves the remaining balance. Either policy skips a proof when its smallest possible exact promotion certificate cannot fit. An eight-case panel with minimum gain one requires at least nine reads. The same exact proof rule determines promotion and every issued read is charged.

The two shorter policies use the published adaptive order. The older full-quote adaptive and direct-only queues are controls. The other family selects a policy by exact promotions and then lower cost. A positive paired lower endpoint against the single proof is required on all three cohorts within the same allowance.

## Results

| Cohort | Full quote passes / lookups | Base cap passes / lookups | Balance cap passes / lookups |
| --- | ---: | ---: | ---: |
| BBH and LMentry | 17,290 / 72,530 | 17,283 / 72,524 | 17,290 / 72,530 |
| MMLU prior subjects | 21,190 / 34,342 | 21,190 / 34,342 | 21,190 / 34,343 |
| MMLU additional subjects | 8,976 / 13,753 | 8,976 / 13,749 | 8,976 / 13,754 |

Capping proofs at base cost funded three more BBH and LMentry direct proofs, with two fewer promotions and seven fewer held-out passes than the full-quote queue. The paired range was −0.059 to +0.005 percentage points. The same cap funded one extra direct proof on the prior MMLU subjects with identical scores and spend.

The balance cap consumed one more lookup on each MMLU cohort and preserved all holdout totals. Neither shortened policy improved MMLU. The outside-family fits selected direct-only for BBH and LMentry and the full-quote adaptive queue for MMLU. The all-cohort quality gate remained unmet. [All costs, route counts, and paired ranges](witness-short-admission-credit-results-v1.json)

## Reproduce

Use a clean source export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 64 targeted tests passed and two replays matched byte for byte. The full-quote and direct-only controls reproduced their scores, costs, and funded traces. The CLI rejected a stale seal, and the prospective live manifest reproduced byte for byte. Storage Guard measured 6.5 GiB free. The export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Reservation tests](../tests/unit/test_witness_short_admission_credit.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_short_admission_credit
python -B -m benchmarks.witness_short_admission_credit \
  --execute a816b5919252a4900567c641a1a45d601c71f56b3d795f92c3cb36038e301f74 \
  --out NEW_REPORT.json
```
