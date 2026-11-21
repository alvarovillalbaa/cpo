# Measure how much a wider backup search could recover

The one-read backup test completed new validation certificates on AIME and changed zero deployments. This audit fixes every paid reply and deployment from the seeded CPO run. On a retained trial with a primary training veto and no paid validation backup, it checks every other prompt in the original roster. A backup must strictly beat the incumbent on the original validation, training corroboration, and independent qualification panels. [One-read result](recorded-one-read-backup.md) · [Audit runner](../benchmarks/recorded_training_veto_backup_ceiling.py)

The audit prices only the minimum extra replies that could prove those outcomes. It credits paid incumbent replies, charges the primary training veto where it still needs proof, and keeps all prior search and qualification costs. It lets hindsight pick favorable unread replies and the best held-out backup, including choosing to keep the start. The result bounds the specified backup-only change with the existing gates and fixed paid prefix. A deployable allocator would have to choose without access to those outcomes.

| Archived setting | Retained trials with a training veto and no paid backup | Extra passes with one new validation read | With two reads | With three reads | Full-width ceiling | Minimum added lookups at full ceiling |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIME root, eight challengers | 12 | 0 | 0 | 1 | 1 | 17 |
| AIME rotation, four challengers | 91 | 0 | 0 | 0 | 0 | 0 |
| AIME rotation, eight challengers | 88 | 0 | 0 | 3 | 3 | 23 |
| ARC-AGI rotation, four challengers | 60 | 0 | 25 | 25 | 69 | 132 |
| ARC-AGI rotation, eight challengers | 60 | 0 | 0 | 6 | 72 | 279 |

The AIME eight-challenger rotation offered helpful backups on two of 88 eligible retention trials. Both needed three more validation passes. The ceiling rose from 4,073 to 4,076 holdout passes, and the optimistic cost rose from 12,164 to 12,187 lookups. The 10% saving against the cheaper matched GEPA arm allows 12,057. The ARC eight-challenger rotation had more room for quality, with 72 possible gains across 11 trials. Its optimistic cost was 10,175 versus the 9,631-lookup gate. The AIME four-challenger root and both ARC roots yielded zero gains. [All cohorts, role-level proof costs, and matched controls](recorded-training-veto-backup-ceiling-results-v1.json)

On the two eight-challenger rotations, the existing search and qualification cost already exceeds the lookup ceiling. Widening the backup search on top of that paid prefix cannot meet the combined gate. The result leaves open policies that change the earlier acquisition budget or the nomination before those costs are incurred.

A follow-up stopped validation at the first proved gain. It saved 3,973 lookups and added nine passes on the eight-challenger AIME rotation, while losing passes on ARC. [First-certificate replay](recorded-first-training-certificate.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 26 targeted tests passed and two replays matched byte for byte. The seeded path reproduced all eight archived score, cost, and trace totals. The CLI rejected a stale seal, and the ordered live plan reproduced. Storage Guard measured 6.0 GiB free. The 39 MiB export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Cost and eligibility tests](../tests/unit/test_recorded_training_veto_backup_ceiling.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_training_veto_backup_ceiling
python -B -m benchmarks.recorded_training_veto_backup_ceiling \
  --execute 1f6c56938e1888a11260a800bccbf8862472424c9fc13db9f6c7cde45f52bcf9 \
  --out NEW_REPORT.json
```
