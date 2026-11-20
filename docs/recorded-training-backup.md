# Use training evidence to choose a validated backup

The five-case training check improved strict CPO on the archived AIME rotation. When it vetoed a move, CPO could only keep the start. This follow-up moves that check before independent qualification and gives it an optional second validation-proven candidate. It reuses the ARC-AGI and AIME pools, all split seeds, candidate rosters, the 180-lookup search ceiling, and the held-out evaluation. [Training corroboration](recorded-training-corroboration.md) · [Replay runner](../benchmarks/recorded_training_backup.py)

## Policies

- **Training after qualification** reproduces the earlier first-half check. The chosen challenger needs a strict gain on both independent qualification and the first half of the training panel.
- **Training before qualification** applies those same checks in the opposite order. Each trial must deploy the same prompt as the previous policy.
- **Fully scored backup** checks the strict validation winner on training first. If it lacks support, the best other fully scored validation improver can try the same training check.
- **Certified backup** also allows a partially scored candidate whose paid replies already prove a strict validation gain and preserve the incumbent's measured critical passes. Candidates are ordered by confirmed passes, with proposal order breaking ties.

Each backup policy considers at most one alternate. It reserves enough room to complete its training proof and reuses any incumbent replies from the first check. Only the resulting nominee faces independent qualification. The experiment reproduces the earlier strict CPO and both official GEPA comparison traces. [Recorded ARC and AIME pools](recorded-math-validation-ties.md)

The incumbent precheck pays for qualification replies until the first miss. If the incumbent passes every case, a strict qualification gain is impossible and search can stop before evaluating challengers. Otherwise, independent qualification reuses the incumbent replies already paid for. The candidate ranking receives only search and training evidence. The replay reports the precheck on the certified backup and on both GEPA controls to measure the gain from sharing this rule.

## Results

Each cell reports holdout passes / paid lookups. Rotation trials use each non-root prompt in the archive as the incumbent.

| Policy | AIME, 4 challengers | AIME, 8 challengers | ARC-AGI, 8 challengers |
| --- | ---: | ---: | ---: |
| Retain start | 4,056 / 0 | 4,056 / 0 | 12,944 / 0 |
| Strict CPO | 4,036 / 7,726 | 4,002 / 11,166 | 13,932 / 10,383 |
| Training after qualification | 4,069 / 8,208 | 4,062 / 11,749 | 13,818 / 11,886 |
| Training before qualification | 4,069 / 8,562 | 4,062 / 12,176 | 13,818 / 12,883 |
| Fully scored backup | 4,073 / 8,809 | 4,068 / 12,563 | 13,818 / 13,067 |
| Certified backup | 4,078 / 8,830 | 4,073 / 12,575 | 13,822 / 13,087 |
| Certified backup with precheck | 4,078 / 8,936 | 4,073 / 12,534 | 13,822 / 10,589 |
| Batched GEPA with precheck | 4,067 / 8,509 | 4,055 / 13,410 | 13,781 / 10,785 |
| Sequential GEPA with precheck | 4,079 / 9,036 | 4,074 / 13,720 | 13,785 / 11,962 |

On the eight-challenger AIME rotation, a paid validation certificate identified an alternate in 60 trials. Sixteen passed the training check and six cleared independent qualification. This recovered 11 held-out passes over the training veto, with a paired case sensitivity range of −8 to +31. With the same precheck on both GEPA controls, the policy finished one pass behind sequential GEPA and 18 passes ahead of batched GEPA. It saved 8.6% and 6.5% of paid lookups, respectively, below the 10% requirement against both. The joint range against the matched controls was −23 to +22 passes. At four challengers, the precheck added 106 certified-backup lookups and the policy used 5.0% more than batched GEPA with the same precheck. Keeping the original AIME root scored 500 passes and exceeded every backup setting tested on that root. [Full results and paired ranges](recorded-training-backup-results-v1.json)

On the eight-challenger ARC rotation, the precheck skipped 106 searches and cut the certified backup's paid lookups by 2,498. The matched saving against batched GEPA was 1.8% and strict CPO scored 110 more passes on 206 fewer lookups. Every matched backup comparison missed the archived superiority gate. These findings apply to retrospectively chosen training cases and stored model replies. Fresh-model qualification remains pending.

A follow-up tested whether protecting the same validation replies could recover the gains without a separate training check. It also measured the incumbent precheck on strict CPO. [Validation stability replay](recorded-validation-stability.md)

## Reproduce

Use GEPA 0.1.4 and the bundled score snapshot. Preview the plan seal, then run to a fresh report path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_training_backup
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_training_backup \
  --execute 93ba18473387eb885d5bfe6f0cca2f4d043795b3fbc91f17abe274445c7b144c \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked. They reproduced the 40 published comparison traces, checked 1,520 reordering decisions and 4,560 matched precheck decisions, and rejected a wrong seal and reuse of an existing output path. Five focused tests passed. Storage Guard measured 16.4 GiB free. The temporary wheel and source overlay used about 15.3 MB under the standing LAB exception and was removed after verification. [Focused tests](../tests/unit/test_recorded_training_backup.py)
