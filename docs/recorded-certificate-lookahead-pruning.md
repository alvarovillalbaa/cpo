# Skip validation reads that cannot change the nominee

The one-panel lookahead fell 42 lookups short of the LMentry cost gate. This replay checks each scheduled read of the first certified prompt before buying it. It asks whether any later challenger could still prove a two-pass validation gain after that read while keeping its training reserve. The check counts known passes and protected cases, then gives the challenger every remaining reply in its favor. If even that completion cannot fit, the original schedule will nominate the first prompt regardless of its next grade, so the replay skips the read and keeps that prompt. [Original lookahead](recorded-certificate-lookahead.md) · [Pruning runner](../benchmarks/recorded_certificate_lookahead_pruning.py)

The replay compared every original and pruned path on the same 2,352 archived trials for each allowance. It verified the same nominee, deployment, and held-out grades on all 4,704 comparisons. The one-panel allowance saved 66 validation lookups, and the two-panel allowance saved 15. Qualification lookup counts stayed the same. Some omitted replies would have strengthened the first prompt's certificate, even though the independent checks would still receive that same prompt.

| Setting | One-panel lookups before → after | Two-panel lookups before → after |
| --- | ---: | ---: |
| AIME, eight-challenger rotation | 8,701 → 8,692 | 9,461 → 9,461 |
| ARC-AGI, eight-challenger rotation | 8,598 → 8,586 | 8,942 → 8,941 |
| MMLU | 10,981 → 10,979 | 11,661 → 11,661 |
| BBH | 8,628 → 8,619 | 9,277 → 9,275 |
| LMentry | 4,704 → 4,693 | 4,985 → 4,977 |

On LMentry, the one-panel rule saved 9.4% against the cheaper GEPA control, 31 lookups short of the 10% requirement. The two-panel rule retained its positive joint quality range of +25 to +68 passes and saved 3.9% against that control. Every cohort kept its previous gate outcome. This exact shortcut removes a small part of the lookahead cost. The replay leaves room to change which challengers receive lookahead or how it ranks them. [All settings and paired decisions](recorded-certificate-lookahead-pruning-results-v1.json)

A follow-up tested later challengers first and measured the cost of requiring a strict validation gain over the first certified prompt. [Head-to-head replay](recorded-certificate-head-to-head.md)

## Reproduce

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 31 targeted tests passed and two replays matched byte for byte. The bound tests enumerate unread reply patterns at several budgets and check that later challengers retain their training reserve. The CLI rejected a stale seal, and the ordered live plan reproduced. Storage Guard measured 5.9 GiB free. The 40 MiB export and publication worktree fit the standing 0.2 GiB LAB exception. The replay made zero provider requests. [Bound tests](../tests/unit/test_recorded_certificate_lookahead_pruning.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_certificate_lookahead_pruning
python -B -m benchmarks.recorded_certificate_lookahead_pruning \
  --execute 8792577f81661f7065005f716ff2aeef6804820f87f4609c9c5e73296720bc5b \
  --out NEW_REPORT.json
```
