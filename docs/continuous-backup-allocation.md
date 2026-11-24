# Allocate terminal backup lookups across tasks

The preservation requirement excluded many of the productive backups in the previous replay. This experiment restores the original eligibility rules and forecasts. The settled primary cycles, proof, start quotes, per-task candidate order and cohort lookup ceilings stay fixed. For both paid repair and one probe, the comparison changes which task receives the next affordable backup attempt. [Terminal backup study](continuous-archive-backup.md) · [Preservation experiment](continuous-backup-guard.md) · [Replay runner](../benchmarks/continuous_backup_allocation.py)

- **Global priority** reproduces the original probability-ranked allocation.
- **Equal charge** chooses the task with the fewest settled backup lookups and uses the original priority to break ties.
- **Charge per episode** divides each task's settled backup lookups by its number of eligible episodes before comparing tasks.
- **Discounted priority** keeps the probability comparison across tasks and discounts a task's priority by its spend relative to its share of the cohort budget. The share is proportional to the number of eligible episodes.

The cohort balance refunds unused reserve after each attempt. A task can keep spending when other queues have no affordable offer. Promotion still requires an exact gain on the original independent qualification cases. The allocator can see settled costs and the original paid candidate evidence.

The hindsight diagnostic prices every eligible positive-gain backup at its actual proof charge. It computes a pooled upper bound and a task-specific upper bound that holds each task to the amount it spent in the replay. The latter relaxes the timing of quote reservations and keeps each offer's original individual quote affordable at the cohort ceiling. The difference between these bounds includes any unspent cohort balance. It shows how much a hindsight selector could gain by changing task allocations, beyond improvements available within the original charges.

A stricter replay caps each alternative at the lookups the global policy actually spent on that cohort. It compares the resulting deployments with the archived global policy run under its original ceiling. The stricter ceiling can prevent an attempt that the original policy started with more available reserve.

## Results

These totals cover seven cohorts and 2,048 episodes. The first two columns give held-out pass gains and additional lookups over joint qualification without backups. The final column gives pass and lookup changes from the original global policy when the alternative starts under its stricter ceiling.

| Backup mode and allocator | Passes gained | Backup lookups | Change under stricter ceiling |
| --- | ---: | ---: | ---: |
| Paid repair, global priority | +51 | 299 | — |
| Paid repair, equal charge | +57 | 300 | +6 passes / −14 lookups |
| Paid repair, charge per episode | +51 | 299 | +3 passes / −14 lookups |
| Paid repair, discounted priority | +51 | 300 | +2 passes / −18 lookups |
| One probe, global priority | +54 | 562 | — |
| One probe, equal charge | +67 | 564 | +8 passes / −20 lookups |
| One probe, charge per episode | +66 | 563 | +12 passes / −17 lookups |
| One probe, discounted priority | +51 | 564 | 0 passes / −18 lookups |

For one probe, equal charge gained 11 passes over the global policy on bounded LMentry for two extra lookups. Its paired 95% range was +2 to +20. It scored 25 passes above the budget-matched subject-tuned simple controls there, with a paired range of −48 to +96. Under the stricter ceiling, charge per episode gained six passes on bounded LMentry, two on tie BBH and four on tie LMentry. Their individual paired ranges against global priority each crossed zero.

On bounded LMentry, equal-charge one probe moved the ends-with-word task from 26 backup lookups to eight and rhyming word from two to 12. With the original global task charges, hindsight could gain at most 52 passes there. The pooled settled-charge ceiling was 95. For all seven cohorts, holding the global one-probe task charges fixed gave a hindsight upper bound of 138 passes, against 197 pooled and 54 observed. Under the relaxed quote timing, the ceiling leaves up to 84 passes within the original charges and another 59 if hindsight can change task budgets or spend the remaining balance.

[Bounded BBH](continuous-backup-allocation-bounded-bbh-v1.json) · [Bounded LMentry](continuous-backup-allocation-bounded-lmentry-v1.json) · [Bounded MMLU](continuous-backup-allocation-bounded-mmlu-v1.json) · [Four-case MMLU](continuous-backup-allocation-four-case-mmlu-v1.json) · [Tie BBH](continuous-backup-allocation-tie-bbh-v1.json) · [Tie LMentry](continuous-backup-allocation-tie-lmentry-v1.json) · [Additional MMLU](continuous-backup-allocation-additional-mmlu-v1.json)

The replay selected among archived candidates on cohorts used in earlier comparisons. Paired ranges resample cases within task with the selected comparator settings fixed. Live optimization quality remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Preview a different cohort's seal by omitting `--execute` and `--out`. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_backup_allocation \
  --cohort bounded-LMentry \
  --execute 0ac5e0365bb7a1d293c53f0b7460212109527af1278bc8034ad45ef3f93c27ab \
  --out NEW_REPORT.json
```

Nineteen targeted tests passed. Two CLI replays per cohort matched byte for byte with DNS and outbound sockets blocked. All global dispatch receipts reproduced and all task charges reconciled with the cohort budgets. Storage Guard measured 10.0 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_continuous_backup_allocation.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
