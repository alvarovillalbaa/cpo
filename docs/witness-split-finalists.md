# Let the second finalist repair a different paid miss

The earlier first-proof rankers could choose from many paid MMLU candidates and retained every original nominee. This comparison changes the rotating screen that generates those choices. The normal incumbent scan, first eligible finalist, candidate order, and per-cycle lookup cap stay fixed. After the first finalist, the screen seeks its second finalist on a different already-paid incumbent miss when one is available. Both finalists preserve the same sampled incumbent pass when available. A shared tie case is separate from both repair witnesses and the preservation case. It ranks both finalists when two replies fit the cap. [First-proof fit](witness-first-proof-fit.md) · [Rotating screen](rotating-witness-cycle.md) · [Replay runner](../benchmarks/witness_split_finalists.py)

One arm draws its second miss from the current scan. The primary arm may also use a miss from a previous witness cycle of the same episode. Both arms follow the existing scan, including its stopping rule. They make no additional incumbent reads to find an alternate. When one is unavailable the screen uses the original shared miss. The original cap-16 Halving fallback still runs only if the witness stage makes no nomination. Each arm pays for distinct search lookups and at most one exact proof, with the original independent panel and tie extension.

The primary comparison requires a positive paired lower endpoint against the original expected-read proof and no higher cost than seeded CPO on each cohort. The report also records the strongest published fixed GEPA control affordable at each arm's realized lookups. Those fixed points come from the previously verified native grid. They provide a separate point comparison on the archived prompts. [Native GEPA comparison](witness-cached-gepa-evidence.md)

## Results

| Cohort | Original passes / lookups | Current-scan split passes / lookups | Paid-cache split passes / lookups | Best affordable fixed GEPA passes / lookups for paid-cache split |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,022 / 71,437 | 17,016 / 71,576 | 16,083 / 60,211 |
| MMLU prior subjects | 21,180 / 34,122 | 21,180 / 34,245 | 21,189 / 34,540 | 21,159 / 30,096 |
| MMLU additional subjects | 8,976 / 13,639 | 8,976 / 13,743 | 8,977 / 13,911 | 8,976 / 13,219 |

The paid-cache rule gained ten pooled MMLU passes for 690 additional lookups. It exceeded seeded spend by 197 lookups on the prior subjects and 157 on the additional subjects. Its paired 95% intervals against the original proof were 0.000 to +0.069 percentage points and −0.024 to +0.071, respectively. The current-scan rule stayed within seeded spend on both MMLU cohorts and reproduced the original scores.

The paid-cache rule issued 2,455 alternate MMLU probes and found 33 split finalist pairs. The alternate won none of those witness screens. The changed search ledger and tie case still changed five episode nominees and two deployments. On BBH and LMentry, the alternate won 70 witness screens and the rule changed 86 deployments, with 52 fewer passes and 505 extra lookups. Its paired interval there was −0.485 to +0.208 percentage points. The primary arm missed the transfer gate. All grades were archived and the replay made zero provider requests. [Full counts, traces, and intervals](witness-split-finalists-results-v1.json)

## Reproduce

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel in a clean source export. With sockets and DNS blocked, 75 targeted tests passed and two replays matched byte for byte. The original scores, charges, and proof control traces reproduced. The CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 6.4 GiB free. The export, wheel overlay, and publication worktree used the standing 0.2 GiB LAB exception. [Screen and lookup tests](../tests/unit/test_witness_split_finalists.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_split_finalists
python -B -m benchmarks.witness_split_finalists \
  --execute 7816ad173c438fb0ef74c767d031477a7bd1a7027748d61e55a42a106dbe8d9a \
  --out NEW_REPORT.json
```
