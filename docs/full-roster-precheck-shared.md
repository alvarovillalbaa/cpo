# Share reference replies in the five-arm CPO comparison

The original fixture plan reserved a full extra set of paid replies for the opt-in runner. The shared-reply plan keeps the same tasks, case roles, candidates, comparators and logical budgets. It runs the original four arms in their original seeded order, then runs the opt-in arm on the shared journal. [Original rehearsal](full-roster-precheck.md) · [Shared-reply runner](../benchmarks/full_roster_precheck_shared.py)

Candidate training and admission calls must reuse exact requests already used by packaged feedback. Validation may reuse any matching cached reply. Each cycle can buy at most 18 validation replies solely for the candidate, the widest of its deferred screens. A changed schedule, nominee or selected prompt stops the comparison before holdout scoring. When the decisions agree, the ordinary holdout evaluator grades the shared selected prompt once per case and repeat. [Sealed shared-reply plan](full-roster-precheck-shared-plan-v1.json)

| Role | Original physical ceiling | Shared-reply ceiling |
| --- | ---: | ---: |
| Drafting | 36 | 36 |
| Evaluation | 1,107 | 1,092 |
| Admission | 360 | 288 |
| Development scoring | 648 | 540 |
| **Total** | **2,151** | **1,956** |

The scripted fixture still took 436 physical requests. The candidate reused every reply already available by the time it ran. It matched packaged feedback's decisions and held-out grades and saved seven attributed and logical search requests. The settled-CPO gate remained below its required saving. The lower ceiling bounds requests that may be needed on fresh responses. The scripted result measures the harness. [Fixture verification](full-roster-precheck-shared-verification-v1.json)

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.full_roster_precheck_shared \
  --fixture a0bfebfe028202543e7291829b0c9b08b74d9de4a1308d8c5166052561f6ddfa \
  --out shared-fixture
python -B -m benchmarks.full_roster_precheck_shared \
  --replay shared-fixture --out shared-replay
```

Two fresh fixture runs and the exact journal replay agreed byte for byte. All 27 focused tests passed, including rejection of a new candidate admission request, enforcement of per-cycle validation caps, and stopping before holdout on divergence. Storage Guard measured 7.2 GiB free. The source export, pinned wheel overlay, fixture data and publication checkout fit the standing 0.2 GiB LAB exception. Teardown was verified. [Tests](../tests/unit/test_full_roster_precheck_shared.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
