# Open one backup within a fixed validation allowance

The full-roster audit found that better nominees accounted for most of the remaining gap on rotated AIME and ARC-AGI. This replay measures which of those alternatives had paid validation evidence when the original race stopped. It then tests spending four or eight extra validation reads on one backup after a training veto. [Roster ceiling](recorded-math-roster-ceiling.md) · [Replay runner](../benchmarks/recorded_bounded_certificate_backup.py)

## What the original race could see

For each trial, take the best alternative that passes the original gates and improves on both the actual deployment and the start. Group its extra held-out passes by its paid validation evidence. When the incumbent and challenger already have a strict validation certificate, the audit records zero additional validation reads. Otherwise it counts the minimum number of favorable unread grades required. It assumes the audit can choose the best candidate and the most favorable cases in hindsight, with training and qualification outcomes known.

| Eight-challenger rotation and original policy | Already certified | Partly read | Unprobed | Extra passes at four favorable reads |
| --- | ---: | ---: | ---: | ---: |
| AIME, first certificate | 0 | 0 | 36 | 36 |
| AIME, validation and qualification | 44 | 75 | 4 | 121 |
| ARC-AGI, first certificate | 0 | 0 | 341 | 148 |
| ARC-AGI, validation and qualification | 7 | 170 | 127 | 103 |

The first-certificate race had bought no validation grades for any of the best unselected improvements across 18 rotated AIME trials and 65 rotated ARC-AGI trials at eight challengers. The full validation race on ARC had partial evidence for alternatives carrying 170 passes across 40 trials. The receipt reports the optimistic limit for each allowance from zero through eight and separates the subset reachable after a first-nominee training veto. [Paid evidence and limits](recorded-bounded-certificate-backup-results-v1.json)

Restricting the eight-challenger rotations to later candidates after a training veto reduced the four-read ceiling from 36 to 13 on AIME and from 148 to 52 on ARC-AGI. At eight reads the respective ceilings were 13 and 125. Much of the remaining headroom lies outside the backup trigger even with perfect information.

## Paid backup results

The new rule checks the first strict certificate on training before independent qualification. After a veto, it can open previously unprobed later candidates in roster order. It buys a validation reply only while favorable remaining results can certify a gain within the allowance and the training reserve still fits. It stops at the first backup certificate. The backup must pass its own strict training check before using the single independent qualification attempt. Checking training first also incurs reads on some trials that the original qualification-first rule would have rejected earlier.

| Archive and roster | First certificate passes / lookups | Four-read backup | Eight-read backup |
| --- | ---: | ---: | ---: |
| AIME, original, four challengers | 490 / 912 | 490 / 1,024 | 490 / 1,109 |
| AIME, original, eight challengers | 487 / 1,066 | 487 / 1,188 | 487 / 1,303 |
| AIME, rotated, four challengers | 4,077 / 6,737 | 4,077 / 7,589 | 4,075 / 8,280 |
| AIME, rotated, eight challengers | 4,082 / 8,191 | 4,082 / 9,168 | 4,080 / 10,014 |
| ARC-AGI, original, four challengers | 1,496 / 1,402 | 1,496 / 1,413 | 1,518 / 1,434 |
| ARC-AGI, original, eight challengers | 1,496 / 1,402 | 1,496 / 1,413 | 1,518 / 1,434 |
| ARC-AGI, rotated, four challengers | 13,731 / 7,580 | 13,731 / 8,140 | 13,738 / 8,841 |
| ARC-AGI, rotated, eight challengers | 13,755 / 8,346 | 13,755 / 8,992 | 13,767 / 9,852 |

Four reads bought 15 backup certificates across 151 first-nominee training vetoes on eight-challenger rotated AIME. Five backups reached qualification. Aggregate held-out passes stayed at 4,082, and lookups rose by 977. Eight reads lost two passes at higher cost. On the eight-challenger ARC rotation, four reads certified no backups. Eight reads sent eight replacements into qualification and gained 12 passes for 1,506 additional lookups. Its margin against affordable GEPA was −8 with a paired 95% range of −51 to +32 by lookups, and −17 with a range of −57 to +20 by historical cost. The tested fallback spends more to recover little of the available nomination headroom.

A follow-up tested reranking after full validation using only already-paid strict certificates. The shared-case tie recovered a small AIME gain and regressed on the original ARC-AGI start. [Paid head-to-head comparison](recorded-paid-head-to-head.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two socket- and DNS-blocked runs matched byte for byte and reproduced the original GEPA frontiers. All 57 targeted tests passed from a clean export. An independent audit checked all 3,040 decisions, including the two exact search gates, the independent proof, and the backup allowance. The CLI rejected the stale seal. The public selector receipt and ordered live-plan preview reproduced. Storage Guard measured 2.8 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_bounded_certificate_backup
python -B -m benchmarks.recorded_bounded_certificate_backup \
  --execute ee36e98a374117aeb3f86fede5426425d6ad4c2cd92412bee5af25b0547ab218 \
  --out NEW_REPORT.json
```
