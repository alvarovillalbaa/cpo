# Screen challengers on an incumbent miss and pass

The four-read lookahead narrowed its attention after the first certificate. On disjoint LMentry tasks, GEPA reached higher quality at a lower realized cost. This replay moves the extra evidence earlier so every challenger can earn a place in the shortlist. It uses the original archived rosters, training and qualification reserves, and held-out layouts. [Prior cost frontier](recorded-certificate-cost-frontier.md) · [Runner](../benchmarks/recorded_paired_shortlist.py)

Read the incumbent's validation panel. For rosters larger than two, screen all challengers on its first miss. If more than two survive, screen them on the incumbent's first pass, prioritizing a critical pass when present. If the incumbent missed the entire panel, use its first two misses. Each round can eliminate a challenger that can no longer prove a strict gain or preserve a protected pass. The fixed policy keeps the top half after each screen. Earlier rank breaks ties, starting with roster order. The tie-preserving policy keeps every challenger tied at the cutoff. Both reuse the screening grades in a funded exact validation race among finalists, keep a full training reserve, and attempt independent qualification once.

The comparison holds the shortlist policies fixed and uses the same 175 integer caps for each native GEPA mode. Every archived GEPA cap reproduced its paid lookup and held-out pass totals. The paired resampling retains both models and all seeds within each task and selects the best affordable fixed GEPA setting on each draw. [Panel-level counts and matched comparisons](recorded-paired-shortlist-results-v1.json)

| Archived cohort | Fixed halves passes / lookups | Fixed margin vs. affordable GEPA and paired range | Keep cutoff ties passes / lookups | Keep-ties margin and paired range |
| --- | ---: | ---: | ---: | ---: |
| Disjoint LMentry | 5,119 / 11,794 | +63, −4 to +126 | 5,222 / 16,403 | +17, −49 to +67 |
| Disjoint BBH | 6,471 / 18,990 | −84, −141 to −35 | 6,629 / 29,076 | −123, −187 to −61 |
| Original LMentry on different models | 708 / 4,106 | +66, +37 to +97 | 804 / 6,858 | +126, +88 to +159 |
| Original BBH on different models | 2,976 / 7,476 | −73, −107 to −49 | 3,035 / 11,307 | −97, −137 to −61 |

On six disjoint LMentry tasks, fixed halves added 195 passes for 749 more lookups versus the four-read policy. Its best affordable GEPA comparator was sequential at cap 36, with 5,056 passes and 11,785 lookups. The least expensive GEPA setting reaching the fixed-halves score used 956 more lookups. The paired range crossed zero. Retaining cutoff ties tested 2,214 finalist slots versus 698, adding 103 passes and 4,609 lookups over fixed halves. Neither new policy cleared the disjoint-task quality comparison.

On the two original LMentry tasks with different models, fixed halves added nine passes and saved 202 lookups over the first-certificate policy. It retained the earlier matched-cost advantage there. Both shortlist variants lost to affordable GEPA on the BBH cohorts. These archived results support further testing of the fixed shortlist and leave broader or fresh-model superiority unverified.

Checking both witnesses before the first cut improved the matched-cost margin on disjoint LMentry and gave a positive paired range. BBH remained below GEPA on observed scores. [Screen order comparison](recorded-shortlist-screen-order.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and socket connections blocked, 48 targeted tests passed and two full replays matched byte for byte. The tests covered protected passes, cutoff ties, and the training reserve when a screen cannot fit. The CLI rejected a stale seal, and the ordered live plan preview matched. Storage Guard measured 4.8 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replays sent zero provider requests. [Shortlist tests](../tests/unit/test_recorded_paired_shortlist.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_paired_shortlist
python -B -m benchmarks.recorded_paired_shortlist \
  --execute 533d6a3f874e177b6ea6da933dfc3c7a9ff75162ae72617be86aeb74b5e4bee5 \
  --out NEW_REPORT.json
```
