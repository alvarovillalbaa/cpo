# Validate a chain of training repairs together

In the [interaction transfer](opening-interaction-transfer.md), some instructions needed three witnessed edits. Routed repair paid for full validation after each edit and could consider at most two edits. This comparison holds the opening, proposer, evaluator, and 56-lookup search cap fixed. It allows up to three edits before validating the final instruction.

The chain ranks training probes using the validated opening's outcomes and the pair features. Each subsequent proposal first rechecks the previous training witnesses on the current instruction. A persistent failure can reveal another faulty rule on the same input. A proposal receives only training observations. The last instruction must improve the opening's full exact validation score and preserve its critical passes and family scores. Rejection returns the validated opening. Only the final nominee enters paired qualification. [Runner](../benchmarks/opening_staged_repairs.py)

## Transfer

The comparison reproduced the prior controls on all 36 development panels and evaluated 36 disjoint transfer panels. Each table entry gives exact holdout passes out of 648 and total counted calls on transfer.

| Method | Passes | Calls |
| --- | ---: | ---: |
| Routed repair with pair features | 609 | 2,873 |
| Staged repair | 640 | 2,667 |
| Sequential GEPA | 562 | 2,883 |
| Batched GEPA | 521 | 2,639 |

Staged repair cleared the sequential GEPA gate and preserved every matched critical pass against both GEPA controls. The batched comparison missed the cost gate by 28 calls. Staged repair gained 31 passes and saved 206 calls over routed repair, with two matched critical losses on one panel. On development, it scored 633 passes in 2,706 calls and missed the aggregate gates. One or more panels fell below the minimum score and the batched control used 48 fewer calls. [Sealed results](opening-staged-repairs-results-v1.json)

A probe-order pilot stopped each training batch at the first failure. It saved 56 calls on transfer and lost 11 passes relative to staged repair. Stopping only the opening batch saved 34 calls and lost two passes. It cleared both GEPA gates on the observed transfer cohort, while the same rule missed the gates on development. The confirmation found a critical-case regression on fresh panels. [Shorter opening confirmation](opening-staged-witness-transfer.md)

## Reproduce offline

Use GEPA 0.1.4, the source at commit `67e61484e8fb5d42afccdae829e356d9e584969b`, and a fresh output path to reproduce the original seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_staged_repairs
PYTHONHASHSEED=0 python -B -m benchmarks.opening_staged_repairs \
  --execute 7ecf81d330deb95cab126b78f9576abd76f02a247877eaaee740384f6213430d \
  --out NEW_REPORT.json
```

Two socket- and DNS-blocked replays matched byte for byte. Each exercised 72 scripted interaction panels and 144 native GEPA paths. The runner rejected a wrong seal and kept an existing report. Storage Guard measured 4.6 GiB free and the 29.5 MB scratch export was removed under the standing LAB exception. [Verification receipt](opening-staged-repairs-verification-v1.json)
