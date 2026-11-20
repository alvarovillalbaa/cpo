# Measure what staged repairs add after the shared opening

The combined CPO comparison gives every arm the same rewrite and repair. This ablation tests how much CPO gains by continuing after that opening pair. The control runs the same certified opening screen, then qualifies its nominee with the same family, critical-case, and gain rules used by staged CPO. Its selection uses the original training, validation, and admission cohorts. The two policies share the seeded development and confirmation cases and their two repeats. [Combined comparison](grounded-staged-combined.md) · [Ablation runner](../benchmarks/grounded_staged_opening_ablation.py)

| Fixture | Opening only → staged search uses | Opening only → staged development passes | Opening only → staged confirmation passes |
| --- | ---: | ---: | ---: |
| Every rewrite needs repair | 131 → 165 | 80 → 108 of 108 | 34 → 48 of 48 |
| Ticket rewrite is already correct | 119 → 143 | 84 → 108 of 108 | 36 → 48 of 48 |

Both policies selected the same ticket prompt when the ticket rewrite was already correct. Staged CPO gained passes on warehouse and outage in both fixtures. It gained ticket passes when the ticket rewrite needed repair. Across both phases and fixtures it preserved every matched critical pass the opening-only control achieved. Case resampling kept both replies from each case together. The 95% ranges for added passes were +16 to +40 in development and +6 to +22 in confirmation for the all-faulted fixture, and +14 to +34 and +4 to +20 respectively for the perfect-ticket fixture. [Paired results](grounded-staged-opening-ablation-v1.json)

Opening only met the original gate against batched GEPA in both fixtures through the equal-quality efficiency rule. It lost critical cases to sequential GEPA and failed the overall development gate in both fixtures. Its confirmation scores are diagnostic comparisons on the cases already bound to the staged CPO run. Search uses include the shared proposal, evaluations, and admission calls attributed to each policy. The experiment measures fixed fixture replies. It leaves live repair quality and provider costs open.

A follow-up on recorded model replies found no added passes from staged repair in 240 paths. Opening-only used fewer lookups and matched the staged selections in every path. [Recorded opening ablation](grounded-staged-recorded-opening.md)

## Reproduce offline

Use source from commit `34defe647a9ebb92f927b186f16f90017d1dde6e`, the pinned GEPA 0.1.4 dependency, and a fresh output path. The ablation verifies all three archive files for each published combined development and confirmation fixture before evaluating the matched control outcomes.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.grounded_staged_opening_ablation
PYTHONHASHSEED=0 python -B -m benchmarks.grounded_staged_opening_ablation \
  --execute 29e7ce27d60d320bf937aca137cbbb933a23b4356eb3e7718c7a692eb97ba487 \
  --out NEW_REPORT.json
```

Two executions with sockets and DNS disabled reproduced the report byte for byte. Fourteen focused tests passed. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 5.4 GiB available before the run. The 30.5 MB scratch export was removed under the standing LAB exception. [Verification receipt](grounded-staged-opening-ablation-verification-v1.json)
