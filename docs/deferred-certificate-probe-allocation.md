# Allocate challenger probes and proof reads under the same cap

The paired-order comparison left gaps on BBH and MMLU after GEPA received the same qualification scheduler. This replay changes the search and keeps the eight-challenger roster, six validation cases, four independent qualification cases, 19-lookup search cap, and qualification scheduler fixed. It covers 134 model panels in eight recorded cohorts and reuses each panel's 32 seeded schedules at each qualification margin. [Prior GEPA comparison](paired-order-gepa-comparison.md)

The original screen chooses the first incumbent miss for every challenger probe. The rotating screen gives successive challengers successive incumbent misses in validation order, wrapping when necessary. It preserves deferred probe priority, the full probe reservation, and the exact certificate. The eager race uses the original witness and pays for every roster probe before certifying. Each later read goes to the feasible challenger with the fewest observed misses, then the fewest favorable replies needed for a proof, then the earliest roster position. Every nomination must pass the same strict validation certificate and every deployment must pass the same exact independent qualification. [Replay runner](../benchmarks/deferred_certificate_probe_allocation.py)

## Results

The table gives one-gain holdout passes and paid lookups. The GEPA column bounds the expanded subject-tuned score at the rotating screen's lookup budget using the two published budget points per cohort. A published feasible schedule supplies a lower bound and a published ceiling at an equal or larger budget supplies an upper bound. An equal pair proves the exact score. [Full one- and two-gain results](deferred-certificate-probe-allocation-results-v1.json)

| Cohort | Shared probe | Rotating probes | Shared-probe race | GEPA at rotating budget |
| --- | ---: | ---: | ---: | ---: |
| BBH, original | 9,548 / 16,083 | 9,570 / 15,786 | 9,500 / 17,649 | 9,601–9,646 |
| BBH, other checkpoints on previously studied tasks | 4,843 / 9,059 | 4,854 / 8,924 | 4,861 / 9,733 | 4,906–4,917 |
| BBH, causal judgment | 591 / 1,118 | 624 / 1,111 | 593 / 1,158 | 590 |
| LMentry, original | 5,650 / 8,751 | 5,690 / 8,694 | 5,572 / 10,114 | 5,388–5,417 |
| LMentry, other checkpoints on previously studied tasks | 5,307 / 6,151 | 5,412 / 6,032 | 5,299 / 7,153 | 5,016–5,117 |
| LMentry, ends-with-word | 263 / 1,168 | 304 / 1,193 | 316 / 1,327 | At least 233 |
| Disjoint MMLU | 56,094 / 12,792 | 56,067 / 12,756 | 56,066 / 13,141 | 56,116 |
| Earlier MMLU | 26,619 / 13,583 | 26,647 / 13,453 | 26,621 / 14,020 | 26,654 |

At one gain, rotation added 253 passes and saved 756 lookups in aggregate. It improved the original screen in seven cohorts and also paid fewer lookups in six of those seven. It still trailed an affordable GEPA schedule on both previously studied BBH cohorts and both MMLU cohorts. At two gains it added 99 passes and saved 816 lookups in aggregate, while losing passes in four cohorts. The race added lookups in all sixteen cohort-by-margin comparisons. It lost 87 passes at one gain and gained 64 at two gains.

## Where the better challengers were

The retrospective audit looks for a prompt in the supplied roster that would pass both gates and improve the deployed prompt's held-out score. It then runs each qualifying improvement alone with one probe and five remaining proof reads. At one gain, 714 of 4,288 schedules had a better eligible prompt. In every one of those 714, at least one such prompt could certify using the original shared witness if it received the proof reserve to itself. The baseline had paid that probe for at least one such improvement in 372 schedules. In the other 342 it had paid none. The same held for all 359 two-gain improvement opportunities, split into 167 probed and 192 unprobed schedules.

These counts show that changing the witness expands the set of observed trajectories, while shared-witness feasibility alone did not explain the shortfall. The opportunities depended on how the original screen prioritized candidates and distributed its reserve. A candidate ordering that distinguishes among fundable challengers using information available before certification is the next hypothesis. The audit used held-out grades only after the runs and provides no deployable ordering. The production selector remains unchanged. Fresh-model superiority remains unverified.

## Reproduce offline

Use the pinned GEPA 0.1.4 wheel and a fresh output path. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_certificate_probe_allocation
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_certificate_probe_allocation \
  --execute 9348cf4b424da11c65e1c144332f86089418f9ffd307e9709da76d8d96b47ad0 \
  --out NEW_REPORT.json
```

Two socket-blocked replays from a clean source export reproduced the published baseline's 268 panel-by-margin traces and matched byte for byte at SHA-256 `476e3eb08541a1dd4a078794d5aab90fa5a8a844d7d5124fb283382fdc9f44e1`. Seven targeted tests passed. Storage Guard measured 3.0 GiB free. The disposable source and wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Focused policy tests](../tests/unit/test_deferred_certificate_probe_allocation.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
