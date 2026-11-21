# Compare both witnesses before cutting the shortlist

Fixed halves improved on four-read lookahead on disjoint LMentry tasks, with a paired range that still crossed zero. Its first cut used a single incumbent miss and could discard a challenger before checking an incumbent pass. Keeping every cutoff tie improved the score at a substantially higher lookup cost. This replay tests different ways to spend the same kinds of validation reads before an exact finalist race. [Previous shortlists](recorded-paired-shortlist.md) · [Runner](../benchmarks/recorded_shortlist_screen_order.py)

- **Two witnesses before the cut.** Rank challengers on the same incumbent miss and pass, prioritizing a critical pass when present. Use two misses if the incumbent failed every case. Keep two finalists, breaking ties by the first witness and then original roster order. Skip a second grade only when a favorable reply still leaves its challenger outside the finalists, or the first grade already proves futility.
- **One witness with three finalists.** Read the same incumbent miss across the roster and use the lookup budget for an exact comparison of three finalists. At the first cut, a tied score retains roster order.

Both variants reserve training capacity and use the original exact validation, training corroboration, and single independent qualification. They reproduce both previous shortlist policies, including panel path hashes, and the same sequential and batched GEPA cost frontier. The paired resampling picks the strongest fixed GEPA setting affordable within each policy's realized search and qualification costs on every draw. [Full results and path counts](recorded-shortlist-screen-order-results-v1.json)

| Archived cohort | Two witnesses passes / lookups | Margin vs. best affordable GEPA and paired 95% range | One witness passes / lookups | Margin and paired range |
| --- | ---: | ---: | ---: | ---: |
| Disjoint LMentry | 5,177 / 11,928 | +121, +54 to +184 | 5,129 / 11,844 | +73, +6 to +135 |
| Disjoint BBH | 6,489 / 19,346 | −66, −123 to −17 | 6,523 / 19,351 | −32, −92 to +20 |
| Original LMentry on different models | 745 / 4,434 | +100, +66 to +130 | 726 / 4,264 | +84, +55 to +113 |
| Original BBH on different models | 2,984 / 7,408 | −65, −101 to −40 | 3,000 / 7,575 | −49, −84 to −24 |

On six disjoint LMentry tasks, the two-witness policy added 58 passes for 134 more lookups over fixed halves. The best affordable GEPA was sequential at cap 36, with 5,056 passes and 11,785 lookups. The cheapest GEPA setting reaching the CPO score used 14,488 lookups, 2,560 more than CPO. Buying the second witness for every eligible challenger would have added 1,385 LMentry lookups while producing the same nominees and held-out grades.

Both LMentry comparisons improved. Neither policy established superiority on BBH. These are retrospective policy comparisons on archives already used to choose the screening changes. The paired ranges describe sensitivity to the recorded cases. Independent confirmation of the two-witness policy and fresh model performance remain open.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and socket connections blocked, 50 targeted tests passed and two full replays matched byte for byte. The pruning test enumerated every two-witness board for four prompts at three incumbent targets, with and without a critical pass. A direct archive check compared pruning with reading all eligible second witnesses on 1,408 trials. It preserved nominees, deployments, held-out grades, and qualification cost while saving 4,826 lookups. The CLI rejected a stale seal, and the ordered live plan preview matched. Storage Guard measured 4.8 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests. [Screening tests](../tests/unit/test_recorded_shortlist_screen_order.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_shortlist_screen_order
python -B -m benchmarks.recorded_shortlist_screen_order \
  --execute bbe4d15ad29c63e6f5edec5a0a7b5365b2831c6824dc5776efb97449ffb091fd \
  --out NEW_REPORT.json
```
