# Prove a qualification repair without regressions

`run_regression_free_certificate_cycle` keeps the cap and nominee of the deferred certificate screen with one-gain qualification. It promotes only after it proves one or more repairs and rules out regression on every independent qualification case. It reuses the incumbent grades bought by the original precheck. [Public API](../cpo/regression_free_qualification.py) · [Deferred validation screen](deferred-certificate-cycle.md)

```python
from cpo.regression_free_qualification import run_regression_free_certificate_cycle

result = run_regression_free_certificate_cycle(
    incumbent,
    candidates,
    validation_rows,
    qualification_rows,
    evaluate,
    metric_limit=19,
    qualify=qualify,
)
```

For up to eight qualification cases, the scheduler uses the two paid validation pass counts to estimate fixed pass probabilities of one quarter, one half, or three quarters. It chooses the next reply with the lowest expected remaining lookup count under those independent estimates. One paid regression rejects the nominee. The proof also rejects once a repair is impossible and promotes once a repair is known and all regression risks are resolved. Larger panels use the seeded paired proof with every case protected. The proof pays at most two replies per case, and evaluation callbacks receive the original rows. Callers with their own search can use `certify_regression_free_qualification` with a paid incumbent prefix.

## Archived effects

The experiment froze the full-roster cap at 19 across 134 panels and 32 schedules per panel. It compared ordinary one- and two-gain qualification with a seeded proof that protects every case. The optimized proof reproduced the seeded guard’s validation callbacks, nominees, deployments, and held-out grades across all 4,288 paths. [Guarded scores and paired ranges](deferred-certificate-no-regression-results-v1.json) · [Optimized callback receipts and GEPA bounds](regression-free-qualification-results-v1.json)

| Cohort | Guarded held-out passes | Seeded guard lookups | Optimized guard lookups | Pass change vs ordinary one gain, paired 95% range |
| --- | ---: | ---: | ---: | ---: |
| BBH, original | 9,515 | 16,255 | 16,031 | −33 [−64, −3] |
| BBH, other checkpoints on previously studied tasks | 4,837 | 9,154 | 9,086 | −6 [−15, 3] |
| BBH, causal judgment | 591 | 1,132 | 1,122 | 0 [0, 0] |
| LMentry, original | 5,640 | 8,911 | 8,704 | −10 [−28, 9] |
| LMentry, other checkpoints on previously studied tasks | 5,291 | 6,230 | 6,096 | −16 [−27, −4] |
| LMentry, ends-with-word | 263 | 1,177 | 1,158 | 0 [−4, 4] |
| Disjoint MMLU | 56,105 | 12,958 | 12,929 | +11 [0, 22] |
| Earlier MMLU | 26,619 | 13,786 | 13,710 | 0 [−3, 3] |

Across the archive, optimized ordering saved 767 lookups over the seeded guard. It saved 1,007 lookups on 616 paths and added 240 on 240 paths. On disjoint MMLU it gained 11 passes on four fewer lookups than ordinary one-gain CPO. Subject-tuned GEPA still led that guard by 11 passes at the guard’s budget, and ordinary two-gain CPO used 9,017 lookups for 56,094 passes. The BBH and LMentry losses keep the guard opt-in. Fresh-model performance remains unverified. [Subject-tuned comparison](deferred-certificate-subject-ceiling.md)

## Reproduce

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_certificate_no_regression \
  --execute 2e3b2c4e8717b0b2ce822140b05f2f7d8327f384378486ee66fca6e58f42a2c7 \
  --out NEW_GUARD_REPORT.json
PYTHONHASHSEED=0 python -B -m benchmarks.regression_free_qualification_replay \
  --execute 4d6a0a141818bb101be9cb4fcc8813c76f2ef65a833206c8a0a55d658cd09ee7 \
  --out NEW_OPTIMIZED_REPORT.json
```

Two clean-source seeded reports matched byte for byte at SHA-256 `a9d687e06aefa933aeea8d0516903a1bbedd50b7d025297152f86eced49c0203`. The optimized source and independently installed wheel matched at `7d76ffee3205d12e494b00e069b2c7c5c81e60a627262c8d679e624d306f7990`. The tests exhausted 1,280 four-case boards and prefixes, used an independent exhaustive scheduler on two-row states to check expected costs, and exercised the larger-panel fallback. All 20 targeted source tests and four installed API tests passed. The GEPA-dependent tests used the hash-pinned 0.1.4 wheel in a temporary overlay. Both runners rejected their predecessor seals before writing output. DNS and outbound sockets were blocked. Storage Guard measured 3.1 GiB free, and the export, wheel, and publication worktree fit the standing 0.2 GiB LAB exception. [API tests](../tests/test_regression_free_qualification.py)
