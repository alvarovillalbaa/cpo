# Allocate saved proof reads to stalled searches

The one-read screen failed on all 22 supported-rate MMLU candidates. Direct proofs recovered some held-out passes and exceeded the old budget on the prior MMLU subjects. This replay gives the direct proofs a fixed batch allowance equal to the published savings from expected-read ordering. It preserves the original search and all existing nominations. Each no-nominee episode offers the original supported-rate candidate, if any. [Matched probe](witness-no-nominee-miss.md) · [Runner](../benchmarks/witness_admission_credit.py)

Three orders compare the original schedule, the largest smoothed validation margin, and the largest estimated probability of passing proof. The forecast treats each binary grade as independent conditional on the prompt's paid validation pass rate. It includes a win on the base panel and a base tie followed by a win on the reserve panel. The exact observed grades still decide admission. Funding reserves 24 lookups before dispatch and returns unused reads when the proof settles. The queue stops when the balance cannot cover the next full reservation.

The lookup allowance is fixed from the published archive before the replay. The other benchmark family selects an order by exact promotions, then lower realized spend. Held-out outcomes only test the chosen order. A positive paired lower endpoint against the single proof is required in all three cohorts.

## Results

| Cohort | Credit | Eligible / funded proofs | Spent | Added held-out passes | Paired 95% range vs single proof, percentage points |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 1,463 | 82 / 82 | 1,050 | +78 | +0.057 to +0.327 |
| MMLU prior subjects | 221 | 19 / 12 | 201 | +10 | −0.008 to +0.072 |
| MMLU additional subjects | 115 | 3 / 3 | 53 | 0 | 0 to 0 |

Both training families selected schedule order. Every order funded the full queue on BBH and LMentry and the additional MMLU subjects. On the prior MMLU subjects, the validation-margin and certificate-forecast orders each spent 207 lookups for three promotions and ten added passes. Schedule order spent 201 for four promotions and the same ten passes. The positive paired result on BBH and LMentry stayed within the seeded cost. The all-cohort quality gate remained unmet. [All orders and cost receipts](witness-admission-credit-results-v1.json)

Sharing the budget with exact-rejection retries added up to 222 BBH and LMentry passes over the single proof within seeded cost. The shared priority selected for MMLU tied the single proof. [Shared budget benchmark](witness-shared-admission-credit.md)

## Reproduce

Use a clean export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 55 targeted tests passed and two replays matched byte for byte. The full supported-rate queue and the original controls reproduced their scores and costs. The CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 4.4 GiB free. The source export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Ordering and reservation tests](../tests/unit/test_witness_admission_credit.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_admission_credit
python -B -m benchmarks.witness_admission_credit \
  --execute 92229640f592bded522932ebfe7564fea005a66807a0d50992ac7475d596cd76 \
  --out NEW_REPORT.json
```
