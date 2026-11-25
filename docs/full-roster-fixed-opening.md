# Test full-roster CPO without training probes

The published full-roster runner buys up to two incumbent training replies to choose its opening schedule. This replay asks whether choosing that schedule in advance can improve the tradeoff between held-out passes and lookups. It runs each of the three existing opening schedules without training callbacks and keeps the published validation and independent four-case qualification rules. [Benchmark](../benchmarks/full_roster_fixed_opening.py) · [Published runner](full-roster-precheck.md)

AIME and ARC-AGI each use the same two hashed case folds as the earlier math cross-fit study. Each calibration direction compares the three fixed openings and the original adaptive runner. It chooses the highest-scoring option that fits the adaptive runner's realized calibration budget, breaking ties by lower spend and then setting name. The split-safe GEPA sweep and incumbent retention use that same calibration budget. A shared hard per-trial ceiling of 29 covers search and up to eight qualification lookups. The audit runs only the selected settings and the original adaptive runner on the other fold. [Fold construction and comparison limits](recorded-math-budget-crossfit.md) · [Parent math transfer](full-roster-precheck-math.md)

The table sums held-out passes and actual lookups across both audit directions and 3,040 trials. “Calibrated CPO” includes the original adaptive runner when it won calibration. The native control could select free retention. [Sealed replay receipt](full-roster-fixed-opening-v1.json)

| Archive, starting prompt, roster | Adaptive CPO | Calibrated CPO | Calibrated GEPA or retention |
| --- | ---: | ---: | ---: |
| AIME, root, four | 316 / 1,082 | 311 / 611 | 311 / 518 |
| AIME, root, eight | 313 / 1,006 | 311 / 502 | 311 / 518 |
| AIME, rotated, four | 2,538 / 7,909 | 2,542 / 7,922 | 2,506 / 7,848 |
| AIME, rotated, eight | 2,537 / 7,653 | 2,526 / 5,156 | 2,503 / 2,658 |
| ARC-AGI, root, four | 1,051 / 1,262 | 1,108 / 1,119 | 769 / 1,217 |
| ARC-AGI, root, eight | 972 / 1,108 | 1,042 / 875 | 432 / 0 |
| ARC-AGI, rotated, four | 10,612 / 4,934 | 10,612 / 4,934 | 10,378 / 4,792 |
| ARC-AGI, rotated, eight | 10,568 / 4,376 | 10,561 / 3,958 | 10,305 / 4,073 |

Both ARC-AGI root calibration directions chose the fixed uniform schedule. Its paired 95% case ranges against adaptive CPO were +43 to +71 passes at four challengers and +44 to +98 at eight. The eight-challenger root control selected retention in both directions. On rotated ARC-AGI, calibration kept the adaptive runner in both four-challenger directions and in one eight-challenger direction.

On the eight-challenger AIME rotation the calibrated CPO saved 2,497 lookups versus adaptive CPO, with 11 fewer passes and a paired range of −36 to +12. Against calibrated GEPA or retention it gained 23 passes at 2,498 additional lookups. That paired range was −13 to +60. The replay supports dropping training probes for the audited ARC root setting. The AIME quality and cost tradeoff remains unresolved. Both archives have been used for prior CPO research. These paired case ranges are conditional on the selected settings and partitions, and live performance remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. The CLI without arguments previews the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.full_roster_fixed_opening \
  --execute 591d483b0a4bbeb141935111cc9afbdac29e8b21cda1655b9bf668c8d6a006ef \
  --out NEW_REPORT.json
```

Two runs with DNS and sockets blocked produced byte-identical receipts. Eighteen focused tests passed. The CLI rejected a stale seal and preserved an existing output. The replay sent zero provider requests. Storage Guard measured 9.3 GiB free. The isolated source export, pinned wheel overlay, and publication worktree used 122 MiB under the standing 0.2 GiB LAB exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
