# Try one more validation reply after a training veto

Reordering the full validation race changed which backups had enough paid evidence and regressed on AIME. This replay keeps the seeded race and its existing paid backup rule. Only when the primary prompt fails its training check and there is no eligible paid backup can CPO buy one missing validation reply. It buys that reply only if a pass would establish a strict gain and preserve all incumbent critical passes. The resulting backup must still beat the incumbent on the original training and independent qualification panels. [Validation-order results](recorded-validation-race-order.md) · [Replay runner](../benchmarks/recorded_one_read_backup.py)

The selector reserves both training checks and the extra validation read under the original search cap. It ranks eligible alternatives by confirmed validation passes, then by the smoothed pass rate on the missing case from replies already paid for on that case. The seeded roster and case order break ties. When a probe is possible, the primary training check must precede qualification because its result determines who receives the single qualification slot. That ordering can add cost on trials where the seeded policy would have stopped after a qualification failure.

| Setting | Extra validation replies | Strict certificates | Backups entering qualification | Promotions | Added total lookups |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIME root, four challengers | 2 | 2 | 0 | 0 | 19 |
| AIME root, eight challengers | 2 | 2 | 0 | 0 | 19 |
| AIME rotation, four challengers | 8 | 6 | 1 | 0 | 33 |
| AIME rotation, eight challengers | 7 | 6 | 0 | 0 | 86 |
| All four ARC-AGI settings | 0 | 0 | 0 | 0 | 0 |

Every deployed prompt stayed the same across 1,520 trials. All six newly certified backups in the eight-challenger AIME rotation failed the training check. Its total rose from 12,164 to 12,250 lookups at the same 4,073 holdout passes. An optimistic check ranked every offered one-read option using archived replies, required exact training and qualification gains, and retained the incumbent if all valid options lost holdout passes. It found zero additional passes on the offered trials. This bounds the tested options and trigger. A different trigger or a wider validation allowance can expose other candidates. The replay gives no quality or cost reason to adopt this rule. [All scores, matched GEPA controls, and proof counts](recorded-one-read-backup-results-v1.json)

An audit of every backup in the same roster found at most three additional AIME passes on the eight-challenger rotation, at a minimum of 23 extra lookups. [Backup ceiling](recorded-training-veto-backup-ceiling.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 24 targeted tests passed and two replays matched byte for byte. The CLI rejected a stale seal and the original ordered live plan reproduced. Storage Guard measured 6.0 GiB free. The 39 MiB export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests. [Probe and reservation tests](../tests/unit/test_recorded_one_read_backup.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_one_read_backup
python -B -m benchmarks.recorded_one_read_backup \
  --execute fdcaa610443c9684a164f454f52f0febd0da7225e700bf54c6eb2f0416d2abe4 \
  --out NEW_REPORT.json
```
