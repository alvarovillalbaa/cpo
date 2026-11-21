# Race candidates on four shared validation cases

Splitting the repair witness across two incumbent misses changed few MMLU deployments and exceeded seeded cost. This replay replaces the rotating screen with a matched score on four scheduled cases. It uses the first four cases in the original seeded validation order for both the incumbent and every challenger. The original proposal order and cycle search cap still apply. [Split-finalist results](witness-split-finalists.md) · [Replay runner](../benchmarks/witness_matched_anchors.py)

The first-gain arm stops when the existing exact certificate proves that a candidate beats the incumbent on those four cases. The best-score arm uses the package's bounded pool race and takes the highest completed strict gain. If the incumbent passes all four cases, the screen retains it without reading a challenger. Both routes use the original cap-16 Halving fallback after an empty witness stage. One exact independent proof checks any nominee on the original qualification panel. Every distinct search reply and every proof reply is charged.

The primary best-score arm requires a positive paired lower endpoint against the original expected-read proof within seeded CPO spend in all three cohorts. The original search trace and both proof controls are reproduced, and each arm is matched to the strongest published fixed GEPA point it can afford. [Fixed native grid](witness-cached-gepa-evidence.md)

## Results

| Cohort | Original passes / lookups | Four-case first gain passes / lookups | Four-case best score passes / lookups | Best affordable fixed GEPA for four-case best score |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 16,432 / 65,671 | 17,348 / 82,961 | 16,616 / 76,764 |
| MMLU prior subjects | 21,180 / 34,122 | 21,206 / 52,770 | 21,216 / 44,184 | 21,186 / 39,468 |
| MMLU additional subjects | 8,976 / 13,639 | 8,955 / 19,347 | 8,950 / 17,277 | 8,981 / 14,826 |

The best-score arm changed 868 BBH and LMentry nominees and gained 280 held-out passes at 11,890 additional lookups. Its paired 95% interval was +0.005 to +1.347 percentage points against the original. It exceeded the seeded lookup total by 10,427. First-gain selection saved 5,400 lookups and lost 636 passes. Its paired interval was −2.486 to −0.563 points.

On MMLU, best-score search produced 112 nominees in episodes where the original search had none. It gained 36 passes on the prior subjects and lost 26 on the additional subjects. The two paired intervals were −0.134 to +0.200 and −0.553 to +0.215 points. The pooled gain of ten passes took 13,700 additional lookups. It exceeded seeded cost on both cohorts. The original rotating screen's scarcity of new nominees was therefore addressable with matched anchors. The resulting deployments fell short of the quality and cost gate. The replay made zero provider requests. [Complete scores, native settings, activity, and intervals](witness-matched-anchors-results-v1.json)

## Reproduce

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel in a clean source export. With sockets and DNS blocked, 78 targeted tests passed and two complete replays matched byte for byte. The original search and both proof control traces, costs, and scores reproduced. The CLI rejected a stale seal and the prospective live plan reproduced byte for byte. Storage Guard measured 6.3 GiB free. The export, wheel overlay, and publication worktree used the standing 0.2 GiB LAB exception. [Matched-score and cap tests](../tests/unit/test_witness_matched_anchors.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_matched_anchors
python -B -m benchmarks.witness_matched_anchors \
  --execute 2e0caed44248adf110713608e32c2abe12fab26e7f64d206f8e7ca4e343f22ca \
  --out NEW_REPORT.json
```
