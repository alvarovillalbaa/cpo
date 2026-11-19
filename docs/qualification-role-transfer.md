# Extend four-case qualification when it ties

The frozen four-case trial saved lookups and lost 42 passes against eight-case CPO. This follow-up replays the two paths to find where they first differed. It then shortens each qualification role separately and tests adding the four reserved cases when the first four tie. All cohorts were available before this follow-up. [Frozen trial](four-case-qualification-transfer.md) · [Replay runner](../benchmarks/qualification_role_transfer.py)

## Why the shorter panel lost passes

On the 12 transfer panels, four- and eight-case CPO made the same decisions in 345 of 384 episodes. The shorter policy saved 2,323 lookups on those episodes. In the other 39, the first difference was a qualification decision. The four-case panel tied in all 37 episodes where the longer panel alone promoted. In the two episodes where only the shorter panel promoted, it led by one pass after four cases. [Sealed episode attribution](qualification-role-transfer-results-v1.json)

| First different decision | Episodes | Final holdout passes gained / lost by four-case CPO |
| --- | ---: | ---: |
| Fresh challenger promotes only on eight cases | 23 | 3 / 27 |
| Archive retry promotes only on eight cases | 14 | 6 / 33 |
| Archive retry promotes only on four cases | 2 | 11 / 2 |

The observed loss also includes decisions downstream of the first change. Both policies use the same declared search cap. None of these paired paths first diverged by nominating a different fresh candidate.

## Test a tie extension

The tie rule stops on a proven positive or negative gain in the first four cases. An exact tie extends to that cycle's remaining four reserved cases. It retains replies from the first four cases and pays each new reply once. Fresh challengers use the original seeded pair order, while archive retries read incumbent first within each block. Other variants reserve the shorter panel for fresh challengers, all archive retries, retired incumbents, or earlier challengers that never served as incumbent. The experiment uses archived binary outcomes from one task family at a time. Its tie rule leaves the released qualification API untouched. [Contract tests](../tests/unit/test_qualification_role_transfer.py)

| CPO qualification policy | Gemma and Falcon passes / lookups | Flan-UL2 and Mixtral passes / lookups | Transfer passes / lookups |
| --- | ---: | ---: | ---: |
| Eight cases | 8,971 / 21,477 | 18,842 / 31,705 | 22,334 / 29,572 |
| Four cases | 8,989 / 19,028 | 18,871 / 28,422 | 22,292 / 26,411 |
| Short fresh only | 8,993 / 20,157 | 18,842 / 29,854 | 22,316 / 27,865 |
| Short archive only | 8,968 / 20,491 | 18,866 / 30,551 | 22,314 / 28,237 |
| Short retired only | 8,975 / 20,971 | 18,861 / 31,336 | 22,332 / 29,167 |
| Short rejected only | 8,965 / 20,973 | 18,870 / 30,901 | 22,316 / 28,579 |
| Extend ties | 8,979 / 20,520 | 18,901 / 30,839 | 22,343 / 29,052 |
| Original eight-case batched GEPA | 8,996 / 29,285 | 18,866 / 30,649 | 22,352 / 38,990 |

The tie extension gained **76 passes and saved 2,343 lookups** against eight-case CPO across the three cohorts. Moral scenarios accounted for 57 gained passes. Omitting any one subject still leaves a gain of 19 to 78 passes. On the transfer panels, the variant gained 51 passes against four-case CPO and nine against eight-case CPO. It finished nine passes behind batched GEPA and 18 behind sequential GEPA, with 9,938 and 27,452 fewer lookups respectively. The four-case loss motivated the extension, making the gain retrospective. The eight-case default remains in place.

The prospective BBH and LMentry follow-up kept the lookup advantage and scored below all four GEPA controls. [Cross-benchmark transfer](tie-extension-cross-benchmark.md)

## Diagnose the remaining gap

An independent rerun of the eight-case CPO and both primary cap-52 GEPA controls reproduced their transfer traces. Counting the two controls separately, eight-case CPO lost 56 paired episodes. In 22, the final GEPA prompt would have failed to make a strict validation gain on CPO's actual path. In another 12 it would have gained on validation and failed qualification. GEPA retained the starting prompt in 13. CPO missed a challenger that would have passed both gates in eight, and an archive promotion skipped the winner's fresh search in one. These outcomes describe the incumbent and cohort at the cycle where the winning prompt was offered. [Per-episode loss audit](qualification-role-transfer-results-v1.json)

## Reproduce

Use pinned GEPA 0.1.4. The other phases are `development` and `replication`. Each phase has a separate seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_role_transfer --phase transfer
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_role_transfer \
  --phase transfer --execute 9c3a7fa28d239405c34ec70a6734e882264ffac2ccc3ba08ae3d8a28c15df708 \
  --out NEW_REPORT.json
```

Two offline runs per phase produced identical reports. All 64 four- and eight-case CPO baseline traces and 24 transfer GEPA traces reproduced. Three focused tests passed, and a stale seal was rejected before output creation. Storage Guard measured 15.5 GiB free. The 10.9 MB scratch overlay used the standing LAB exception and was removed. Fresh proposal generation and live provider costs remain unverified.
