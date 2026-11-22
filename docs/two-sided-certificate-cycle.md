# Prove validation gains before reading the full incumbent panel

CPO's opt-in two-sided certificate cycle reads the incumbent through its first validation miss. It reserves one shared probe for each admitted challenger and uses the unreserved balance to prove a strict gain. Incumbent reads made during one attempt remain available to later attempts. A challenger that misses the shared probe can still earn a certificate after the positive probes if the balance allows one. [Cycle API](../cpo/two_sided_certificate_cycle.py) · [Original deferred screen](deferred-certificate-cycle.md)

```python
from cpo.two_sided_certificate_cycle import run_two_sided_certificate_cycle

result = run_two_sided_certificate_cycle(
    incumbent,
    candidates,
    validation_rows,
    qualification_rows,
    evaluate,
    metric_limit=19,
    qualify=qualify,
    minimum_gain=1,
)
```

For a panel of width `n`, the fully measured gain is the number of favorable replies minus `n`. A challenger pass or incumbent miss is favorable. The proof can settle the lower bound after `n + 1` favorable replies and must also rule out every critical regression. It stops if a strict gain is impossible or if even the best remaining replies cannot prove it within the allowance. Up to eight validation cases use expected-cost order from paid pass counts and paid same-case counterparts. Larger panels use paired row order. The separate qualification precheck and exact deployment rule still apply. The order can change the budget available for a later challenger.

## Recorded comparison

The replay kept six validation cases, four disjoint qualification cases, eight challengers, and a 19-lookup cap across 134 archived model panels, 32 schedules, and two qualification margins. The public expected-order cycle and the row-order diagnostic preserved every recorded nominee and deployment. The table gives one-gain held-out passes and paid lookups, with total lookup savings against the prior paired-order cycle. [Replay runner](../benchmarks/deferred_two_sided_certificate.py) · [Costs, paid path hashes, and native GEPA bounds](deferred-two-sided-certificate-results-v1.json)

| Cohort | Held-out passes | Prior lookups | Two-sided lookups | Lookups saved |
| --- | ---: | ---: | ---: | ---: |
| BBH, original | 9,548 | 16,083 | 15,059 | 1,024 |
| BBH, other checkpoints on previously studied tasks | 4,843 | 9,059 | 8,167 | 892 |
| BBH, causal judgment | 591 | 1,118 | 1,006 | 112 |
| LMentry, original | 5,650 | 8,751 | 8,276 | 475 |
| LMentry, other checkpoints on previously studied tasks | 5,307 | 6,151 | 5,794 | 357 |
| LMentry, ends-with-word | 263 | 1,168 | 1,106 | 62 |
| Disjoint MMLU | 56,094 | 12,792 | 12,701 | 91 |
| Earlier MMLU | 26,619 | 13,583 | 13,363 | 220 |
| **Total** | **108,915** | **68,705** | **65,472** | **3,233** |

Expected order saved 3,233 lookups at one gain (4.7%) and 3,044 at two gains (5.2%). It finished 713 of 2,530 successful certificates with incumbent cases still unread. The row-order diagnostic also deferred incumbent reads, but added 4,394 total lookups. The original shared-probe and paired qualification order had already been priced against both native GEPA modes. At the new one-gain budget, the exact expanded GEPA score remains 53 passes ahead on original BBH, 22 ahead on disjoint MMLU, and 35 ahead on earlier MMLU. CPO remains above the published upper bounds on all three LMentry cohorts. The BBH comparison on other checkpoints has only an upper bound at the reduced budget. Fresh-model superiority remains unverified. [Published GEPA settings and bounds](paired-order-gepa-comparison.md)

## Reproduce offline

Use Python 3.12 and the pinned GEPA 0.1.4 benchmark dependency. The source export and separately installed CPO wheel reproduced the report byte for byte at SHA-256 `b50173bfd6964cceb58ae34f8492fc1df00a70f7c25b1bee6ef46530a26de0c4`. The API also reproduced the prototype's paid callback hashes exactly. Thirteen source tests and four installed-wheel tests passed, including 4,096 binary panel, cap, and ordering combinations. DNS and outbound sockets were blocked. Storage Guard measured 2.1 GiB free. The bounded source, wheel, and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_deferred_two_sided_certificate.py) · [Benchmark requirements](../requirements-benchmark.txt) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_two_sided_certificate \
  --execute 0ad2e85adbdfc8dded925a7ab1fb0f1a7b24aed0188df86e5e08fe5f9f55244f \
  --out NEW_REPORT.json
```
