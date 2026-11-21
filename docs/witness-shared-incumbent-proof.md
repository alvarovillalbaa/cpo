# Reuse incumbent replies across two exact proofs

On the rotating-witness schedule, 180 MMLU second attempts had an improving paid rival that passed the full independent proof but exceeded the available balance. Experiments with case order and shorter reservations produced small or null gains. An earlier four-cycle backup protocol reused incumbent replies on the same panel. This comparison applies that mechanism to the latest shared lookup queue. [Rival capacity audit](witness-rival-capacity.md) · [Earlier backup comparison](prompt-backup-qualification.md) · [Runner](../benchmarks/witness_shared_incumbent_proof.py)

Each policy preserves paid search, the first proof, and the original eligible rival ranked from paid validation. It runs a backup only after exact rejection. The published retry uses a disjoint panel. The full-charge control uses the first nominee's allotted base and tie rows and charges every scheduled lookup. The reuse policy uses those same rows and pays only for newly accessed grades. Its only free grades are the incumbent replies recorded in the original proof. Both same-panel policies keep the base panel independent of training, validation, and holdout. Two candidates can face the same panel in an episode, so the final held-out scores remain necessary to measure any generalization gain.

The existing queue retains stalled-search direct offers, reserves the same remaining episode allowance before each retry, and releases unused credit after settlement. Each policy has the original cohort budget and episode order. The direct-only queue and full single proof stay in the comparison. Both outside-family fits use only promotion counts and realized cost. The selected policy needs a positive paired lower endpoint against the full single proof on every cohort.

## Results

| Cohort | Direct-only passes / lookups | Disjoint retry passes / lookups | Same panel, full charge passes / lookups | Same panel, incumbent reuse passes / lookups |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,146 / 72,121 | 17,209 / 72,526 | 17,239 / 72,528 | 17,298 / 72,521 |
| MMLU prior subjects | 21,190 / 34,323 | 21,189 / 34,332 | 21,190 / 34,343 | 21,190 / 34,334 |
| MMLU additional subjects | 8,976 / 13,692 | 8,976 / 13,753 | 8,976 / 13,754 | 8,976 / 13,746 |

On BBH and LMentry, reuse gained 59 passes and saved seven lookups against the full-charge control. Its paired 95% interval was +0.021 to +0.289 percentage points. It gained 89 passes and saved five lookups against disjoint retries, with an interval of −0.017 to +0.471. Reuse settled 23 promotions from 65 retries, with 186 incumbent replies reused.

On MMLU, reuse funded 19 retries with 127 cached incumbent replies. Seventeen ended in exact rejection and two ran out of lookups. The full-charge control funded 16 retries, with nine rejections and seven capped proofs. Both same-panel variants matched the direct-only holdout totals on both cohorts, and each used more lookups than direct-only. Reuse made more retries settle. The tested rivals still yielded zero MMLU retry promotions. This result applies to the frozen ranked rivals and original eligibility thresholds.

The fit on BBH and LMentry selected reuse for MMLU. The fit on MMLU selected direct-only for BBH and LMentry. The paired lower endpoint against the single proof remained positive only on BBH and LMentry, so the overall gate remained unmet. The replay used archived grades with zero provider requests. [Complete paired results and proof counts](witness-shared-incumbent-proof-results-v1.json)

The follow-up priced the entire paid backup roster on the same panels. The MMLU ceiling gained only three additional passes under the original queue budget. [Backup ranking and hindsight ceilings](witness-shared-rival-ranking.md)

## Reproduce

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel in a clean source export. With outbound sockets and DNS disabled, 43 targeted tests passed and two replays produced identical reports. The direct-only and disjoint retry queues reproduced their funded traces, scores, and costs. The CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 6.4 GiB free. The source export, wheel overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Proof accounting tests](../tests/unit/test_witness_shared_incumbent_proof.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_shared_incumbent_proof
python -B -m benchmarks.witness_shared_incumbent_proof \
  --execute b9507a1002b16ba5cf98a51c4cbdd32c1fdb00eb95b376a07c3cb0009c45fc0b \
  --out NEW_REPORT.json
```
