# Compare validation finalists on cases unused by the race

The paid head-to-head comparison could only find ties after exact validation pruned other candidates. This replay buys a separate witness for two prompts with strict paid validation certificates. It keeps the original exact validation winner and uses the existing paid backup rule to choose one runner-up. Both versions take their first two or four cases from the unused second half of the training allocation. The runner-up advances only if it proves a strict paired gain over the validation winner. Ties retain the winner. [Paid head-to-head result](recorded-paid-head-to-head.md) · [Replay runner](../benchmarks/recorded_disjoint_finalist_witness.py)

The witness reserves its complete lookup allowance, credits any paid proof replies, and stops as soon as the exact comparison settles. Case order and the paid validation estimates affect lookup cost. The original validation race and independent qualification panel stay separate. A trial can qualify just one nominee, and a rejection retains the incumbent. The same two widths were applied to the original math schedules and 26 previously archived BBH, LMentry, and MMLU panels without fitting to either set.

## Math archives

| Archive and roster | Original passes / lookups | Two-case witness | Four-case witness |
| --- | ---: | ---: | ---: |
| AIME, original, four challengers | 486 / 1,040 | 490 / 1,067 | 487 / 1,102 |
| AIME, original, eight challengers | 476 / 1,438 | 480 / 1,482 | 477 / 1,538 |
| AIME, rotated, four challengers | 4,036 / 7,643 | 4,032 / 7,830 | 4,046 / 8,056 |
| AIME, rotated, eight challengers | 4,002 / 10,908 | 4,004 / 11,212 | 4,029 / 11,585 |
| ARC-AGI, original, four challengers | 1,561 / 1,302 | 1,562 / 1,350 | 1,556 / 1,417 |
| ARC-AGI, original, eight challengers | 1,578 / 1,502 | 1,578 / 1,560 | 1,572 / 1,633 |
| ARC-AGI, rotated, four challengers | 13,878 / 7,007 | 13,879 / 7,095 | 13,881 / 7,202 |
| ARC-AGI, rotated, eight challengers | 13,932 / 8,239 | 13,933 / 8,356 | 13,934 / 8,490 |

On the eight-challenger AIME rotation, four cases gained 27 passes for 677 extra lookups. It still trailed the best affordable GEPA setting by 51 passes with a paired 95% range of −112 to −18. First-certificate CPO had scored 4,082 with 8,191 lookups. On eight-challenger rotated ARC-AGI, four cases added two passes and 251 lookups. The earlier policy led its lookup-matched GEPA frontier by 197 passes. The four-case witness led its new, more expensive frontier by 166. [Math frontiers and costs](recorded-disjoint-finalist-witness-results-v1.json)

## Language transfer at the common search cap

Both official GEPA modes used the original search cap of 180. Their complete per-panel cost, score, and trace receipts reproduced. The table reports actual search and qualification lookups, which can differ at the same cap. Paired intervals resample case IDs within each subject and keep both checkpoints and repeated episodes together.

| Cohort | Original passes / lookups | Two-case witness | Four-case witness | Sequential GEPA | Batched GEPA |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH | 2,121 / 11,258 | 2,136 / 11,488 | 2,132 / 11,707 | 2,099 / 11,062 | 2,086 / 10,707 |
| LMentry | 939 / 6,106 | 929 / 6,244 | 938 / 6,379 | 833 / 5,246 | 839 / 5,181 |
| MMLU | 13,442 / 12,319 | 13,442 / 12,404 | 13,442 / 12,517 | 13,444 / 14,404 | 13,445 / 14,182 |

Two cases added 15 BBH passes and 230 lookups over the original CPO policy. Its paired 95% range for that gain was −9 to +39. The same rule lost ten passes on LMentry. Both rules added lookups without increasing MMLU scores. The witness does not improve the cost-quality outcome consistently across these archives. [Language paired changes and intervals](recorded-disjoint-finalist-witness-results-v1.json)

A follow-up compared finalists using a reserved portion of the original validation panel. It saved lookups in every tested setting and increased held-out passes on eight-challenger rotated ARC-AGI. [Reserved validation comparison](recorded-validation-tail-finalists.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two socket- and DNS-blocked runs matched byte for byte. An independent audit checked all 4,704 decisions against complete witness, qualification, and holdout grades. All 61 targeted tests passed from a clean export, including paid-only shortlist eligibility, sufficient funding, reply reuse, and one independent proof. The CLI rejected the prior seal. The public selector receipt and ordered live-plan preview reproduced. Storage Guard measured 2.8 GiB free. The source export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_disjoint_finalist_witness
python -B -m benchmarks.recorded_disjoint_finalist_witness \
  --execute 0c17f20bb313cd0c5198414af35a58a8f3920f5c52ade5538857e1a32ec0fc5f \
  --out NEW_REPORT.json
```
