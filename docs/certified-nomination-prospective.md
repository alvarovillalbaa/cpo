# Rehearse a matched comparison of certified nomination

The sealed comparison runs packaged certified CPO, uncapped validation-routed CPO, settled CPO, and native sequential and batched GEPA. Ticket, warehouse, and outage each run three cycles. Each cycle drafts one rewrite and repair from the same sixteen labeled cases. Every arm sees the same ordered pair if both proposals are valid and novel. They share the six validation cases, four independent admission cases, and final holdout. This comparison measures selection from shared drafts and the cost of qualifying those selections. [Sealed plan](certified-nomination-prospective-plan-v1.json) · [Runner](../benchmarks/certified_nomination_prospective.py) · [Packaged API](certified-nomination-episode.md)

Both routed arms must agree on the schedule, nominee, admission decision, and deployment in every cycle before holdout begins. The journal reuses an evaluation or admission reply only when its task, role, prompt, case, and repeat match. Holdout scores the initial prompt and every distinct final prompt on every assigned case and repeat. The inherited development gate requires the per-task score floor and preservation of critical cases. It then checks the score gain or efficiency against all four controls on both logical uses and attributed search requests. The request ceiling counts at most five distinct prompts per holdout case and repeat because the routed arms must agree on their final prompt.

| Role | Request ceiling | Physical fixture requests |
| --- | ---: | ---: |
| Shared drafting | 9 | 9 |
| Training and validation | 1,095 | 160 |
| Admission | 360 | 51 |
| Holdout scoring | 540 | 216 |
| **Total** | **2,004** | **436** |

The rehearsal exercised both opening schedules and a rejected nomination followed by a change in schedule. Certified CPO saved five validation lookups on each of two cycles without changing any routed decision. It used 82 attributed search requests against 92 for uncapped routing, 110 for settled CPO, 148 for sequential GEPA, and 198 for batched GEPA. Both cost tallies agreed. The five arms tied on scripted holdout scores and passed the fixture gate. That verifies the gate and accounting. A fresh-model comparison and independent confirmation remain unrun. [Rehearsal receipt](certified-nomination-prospective-rehearsal-v1.json)

## Reproduce offline

Use Python 3.12 and the pinned GEPA 0.1.4 wheel. Run without arguments to preview the seal.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.certified_nomination_prospective \
  --fixture a0c1e4f73ef9d286598bbba9ff0973df46fb755eab16d1a489afa3212a5e7cbe \
  --out NEW_FIXTURE
python -B -m benchmarks.certified_nomination_prospective \
  --replay NEW_FIXTURE --out REPLAY
```

Two fixture runs and their journal replay matched byte for byte on all four archive files. All 33 focused tests and four subtests passed, including refusal of a stale seal and model-delivered archive, detection of a tampered validation request, and termination before holdout when the routed arms disagree. The rehearsal sent zero provider requests. Storage Guard measured 9.1 GiB free. The source export, pinned GEPA overlay, fixture archives, and publication worktree fit in 130 MiB under the standing LAB exception. [Tests](../tests/unit/test_certified_nomination_prospective.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
