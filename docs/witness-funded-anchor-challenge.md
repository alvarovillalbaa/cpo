# Fund a four-case challenge to the first nominee

The full four-anchor race improved BBH and LMentry at a high lookup cost. This replay keeps the original search and its nominee, and reuses its paid validation grades for a smaller challenge. A backup must already have a paid grade and share all four of the nominee's seeded validation anchors. Each episode can challenge with one backup. [Full matched race](witness-matched-anchors.md) · [Replay runner](../benchmarks/witness_funded_anchor_challenge.py)

The primary arm takes the backup that could prove a strict four-anchor gain with the fewest new reads, then breaks ties by smoothed paid pass rate. The matched control reverses those priorities. Both can buy up to four missing grades. They use smoothed paid rates to decide which prompt to read first and stop as soon as the observed bounds prove a gain or rule out success within the remaining cap. A candidate that proves a strict anchor gain goes to its original independent qualification panel. An unsuccessful challenge uses the original nominee's usual proof.

The difference between seeded proof cost and expected-read proof cost sets a fixed cohort allowance. Before an optional challenge, the ledger reserves the full replacement proof and the authorized fresh validation reads. It then returns unused credit. Avoided original proofs reduce measured total cost. The optional balance excludes those savings. Each arm uses the same episode order and independently reconciles its paid ledger. The primary comparison needs a positive paired lower endpoint against the original first proof within the seeded lookup total in every cohort.

## Results

| Cohort | Original passes / lookups | Funded challenge passes / lookups | Seeded lookup ceiling | Nominee switches |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,085 / 71,890 | 72,534 | 44 |
| MMLU prior subjects | 21,180 / 34,122 | 21,180 / 34,319 | 34,343 | 0 |
| MMLU additional subjects | 8,976 / 13,639 | 8,977 / 13,718 | 13,754 | 1 |

Both ranking policies produced identical settlement traces. On BBH and LMentry, the challenge used 830 new validation reads and 608 replacement proof reads. Switching avoided 619 original proof reads, leaving a net increase of 819 lookups and a gain of 17 held-out passes. The paired 95% interval was −0.170 to +0.298 percentage points.

The two MMLU cohorts spent 276 new validation reads and switched one nominee. The replacement proof rejected the challenger, and retaining the incumbent added one held-out pass on the additional subjects. The paired interval there was −0.024 to +0.071 points. All three cohorts stayed within seeded lookups. The primary arm missed the transfer gate. The replay used archived grades and made zero provider requests. [Full charged, reserved, and avoided lookup counts](witness-funded-anchor-challenge-results-v1.json)

## Reproduce

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel in a clean source export. With sockets and DNS blocked, 85 targeted tests passed and two complete replays matched byte for byte. The original search traces and proof totals reproduced. The CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 6.3 GiB free. The source export, wheel overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Exact bounds and lookup tests](../tests/unit/test_witness_funded_anchor_challenge.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_funded_anchor_challenge
python -B -m benchmarks.witness_funded_anchor_challenge \
  --execute 355d1907339e0a3551b61dabdcb7ee503dac29382bc6ec65bfd4c6f56ed4decb \
  --out NEW_REPORT.json
```
