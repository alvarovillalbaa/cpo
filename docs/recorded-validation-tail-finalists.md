# Reserve the end of validation for finalists

Buying separate comparison cases improved some finalists at higher cost. This replay reserves the last one or two cases from the existing validation panel. It runs the original strict race on the preceding cases, then takes its winner and strongest already-certified backup as finalists. It reads the reserved tail for the feasible finalists and tries the one with more tail passes first, with the prefix winner keeping ties. [Separate witness experiment](recorded-disjoint-finalist-witness.md) · [Replay runner](../benchmarks/recorded_validation_tail_finalists.py)

To advance, a finalist still needs a paid strict gain over the incumbent on the original full validation panel, including every protected incumbent pass. When the pair cannot be funded or neither finalist earns that certificate, the selector can fall back to the full race and reuse paid grades. The original cap and single independent qualification attempt apply throughout. The comparison uses the same math archives and 26 language panels as the separate witness replay. It uses no new evaluation cases, prices, or inference.

## Math archives

| Archive and roster | Full race passes / lookups | One reserved case | Two reserved cases |
| --- | ---: | ---: | ---: |
| AIME, original, four challengers | 486 / 1,040 | 488 / 1,007 | 487 / 984 |
| AIME, original, eight challengers | 476 / 1,438 | 477 / 1,335 | 476 / 1,249 |
| AIME, rotated, four challengers | 4,036 / 7,643 | 4,044 / 7,363 | 4,045 / 7,161 |
| AIME, rotated, eight challengers | 4,002 / 10,908 | 4,022 / 10,201 | 4,015 / 9,618 |
| ARC-AGI, original, four challengers | 1,561 / 1,302 | 1,561 / 1,292 | 1,551 / 1,261 |
| ARC-AGI, original, eight challengers | 1,578 / 1,502 | 1,577 / 1,476 | 1,574 / 1,419 |
| ARC-AGI, rotated, four challengers | 13,878 / 7,007 | 13,853 / 6,934 | 13,866 / 6,865 |
| ARC-AGI, rotated, eight challengers | 13,932 / 8,239 | 13,906 / 8,106 | 13,938 / 7,932 |

On eight-challenger rotated ARC-AGI, two reserved cases gained six passes and saved 307 lookups and $43.42 at recorded prices compared with the full race. The paired range for the six-pass gain was −17 to +30. Omitting one incumbent at a time gave margins of −17 to +18. Its lead over the best affordable GEPA setting was 203 passes on the lookup schedule, with a paired 95% range of +95 to +313. At historical prices the lead was 170 passes, with a range of +74 to +268. On eight-challenger rotated AIME, two cases gained 13 passes and saved 1,290 lookups against the full race, with a paired range of −10 to +37. Affordable GEPA still led by 65 passes, with a paired margin for CPO of −129 to −21. [All cost-matched controls and case ranges](recorded-validation-tail-finalists-results-v1.json)

## Language transfer at the common search cap

| Cohort | Full race passes / lookups | One reserved case | Two reserved cases | Sequential GEPA | Batched GEPA |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH | 2,121 / 11,258 | 2,125 / 10,569 | 2,117 / 9,979 | 2,099 / 11,062 | 2,086 / 10,707 |
| LMentry | 939 / 6,106 | 926 / 5,635 | 924 / 5,219 | 833 / 5,246 | 839 / 5,181 |
| MMLU | 13,442 / 12,319 | 13,449 / 11,814 | 13,444 / 11,464 | 13,444 / 14,404 | 13,445 / 14,182 |

One reserved case gained four BBH passes and saved 689 lookups from full-race CPO, with a paired range of −9 to +17. It gained seven MMLU passes and saved 505 lookups, with a range of zero to +14. It lost 13 LMentry passes while saving 471 lookups. Both widths saved lookups in every math and language setting, and some settings lost held-out passes. The language GEPA comparison reports measured spending for both native modes at their original common cap. [Language comparisons](recorded-validation-tail-finalists-results-v1.json)

A follow-up matched the language policies to 350 realized GEPA cost settings per cohort and tested an optimistic subject-specific cap schedule. [Matched language cost frontier](recorded-validation-tail-language-frontier.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two socket- and DNS-blocked runs matched byte for byte. The original math frontiers and all 26 language control receipts reproduced. An independent audit checked all 4,704 decisions for funded paid validation, independent qualification, and held-out scoring. All 64 targeted tests passed, including 512 exhaustive small validation boards at both widths and three budgets. The stale seal was rejected. The public selector receipt and ordered live-plan preview reproduced. Storage Guard measured 2.6 GiB free. The source export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_validation_tail_finalists
python -B -m benchmarks.recorded_validation_tail_finalists \
  --execute 4c58da531626762a5b7f5f35216558aa2b3b7880cecb4acdace54d42f45d540f \
  --out NEW_REPORT.json
```
