# Schedule paired qualification replies jointly

The earlier three-cycle CPO router beat the strongest common controls on the two tie cohorts. This replay keeps its routing table, paid incumbent precheck, validation reads and nominees. It changes the order of qualification lookups after nomination. Each cycle must deploy the same prompt under the original exact one-gain rule. [Original three-cycle experiment](continuous-archive-routing.md) · [Proof scheduler](../cpo/joint_order_qualification.py)

The original scheduler estimates the next reply using its validation pass rate and any paid grade for the other prompt on the same case. For the remaining replies, it uses marginal rates. The new scheduler models a qualification case as a pair with four possible grade combinations and treats cases as independent draws from that distribution. It uses the conditional rate for a case where one prompt's grade is already known. Dynamic programming scores every next read by its expected total remaining work under that model. The weights only affect the order of lookups. Paid grades determine the exact lower and upper gain bounds, and the same bounds settle promotion or retention.

The fit counts the four joint outcomes on archived qualification pairs for the original router's nominees. It groups the counts by the existing coarse validation pass rates, adds one to every combination and uses pooled counts for unseen groups. It uses 70 discovery panels that exclude all 30 transfer task names. Its source data and original discovery totals are checked against the preceding fit. Transfer uses the same 2,048 episodes and verifies the original ordered lookup hashes in every panel. [Discovery receipt](joint-archive-proof-fit-v1.json)

The hindsight floor counts the fewest additional paid grades that could settle each admitted proof if the scheduler knew which unread replies would support the correct outcome. The floor holds the incumbent precheck fixed. It measures remaining ordering headroom and uses information unavailable to the deployed scheduler.

## Transfer results

| Cohort | Original lookups | Joint-order lookups | Lookups saved | Held-out passes |
| --- | ---: | ---: | ---: | ---: |
| [Bounded BBH](joint-archive-proof-bounded-bbh-v1.json) | 13,797 | 13,715 | 82 | 6,389 |
| [Bounded LMentry](joint-archive-proof-bounded-lmentry-v1.json) | 15,711 | 15,658 | 53 | 6,321 |
| [Bounded MMLU](joint-archive-proof-bounded-mmlu-v1.json) | 7,696 | 7,692 | 4 | 7,725 |
| [Four-case MMLU](joint-archive-proof-four-case-mmlu-v1.json) | 12,145 | 12,040 | 105 | 22,381 |
| [Tie BBH](joint-archive-proof-tie-bbh-v1.json) | 13,130 | 12,906 | 224 | 2,204 |
| [Tie LMentry](joint-archive-proof-tie-lmentry-v1.json) | 7,195 | 7,130 | 65 | 1,028 |
| [Additional MMLU](joint-archive-proof-additional-mmlu-v1.json) | 7,257 | 7,203 | 54 | 7,384 |
| Total | 76,931 | 76,344 | 587 | 53,432 |

All 6,144 cycles preserved the nominee, qualification decision and deployed prompt. The 2,732 nominated paths used 17,133 qualification lookups, down from 17,720, or 3.3%. Total cycle cost fell 0.76%. The new order saved 1,395 lookups across 947 cycles and added 808 across 541 cycles. The hindsight floor was 13,785 lookups on nominated paths, leaving 3,348 lookups above the floor.

On tie BBH and tie LMentry, CPO still exceeded the respective subject-tuned GEPA scores of 2,126 and 919 at the earlier, larger CPO budgets. Those scores are conservative bounds at the lower budget. Repricing uniform and halving controls at the new lookup counts gave subject-tuned scores of 2,172 and 1,013, leaving CPO ahead by 32 and 15 passes. The repriced simple ceiling still scored higher on the other five cohorts. These are comparisons over the same archived candidate rosters. Fresh proposals and live performance remain unverified.

## Reproduce offline

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel. Preview a different cohort by omitting `--execute` and `--out`. [Benchmark requirements](../requirements-benchmark.txt) · [Runner](../benchmarks/joint_archive_proof.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.joint_archive_proof --fit NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.joint_archive_proof \
  --fitted NEW_FIT.json --cohort tie-LMentry \
  --execute fe8dca6b845c2e9c7890c823a9f4ca5af2b12c33676b28e19d32e18a54c58468 \
  --out NEW_REPORT.json
```

Two discovery fits and two source replays per cohort matched byte for byte with DNS and outbound sockets blocked. The documented CLI reproduced the tie LMentry receipt and rejected a fit from the earlier scheduler source. Fifteen targeted tests passed. Storage Guard measured 10.1 GiB free at preflight. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_joint_order_qualification.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
