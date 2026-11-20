# Measure the cost of reaching a stronger prompt in hindsight

Changing how the wide branch scores candidates and picks backups did little on two MMLU cohorts. The earlier reachability audit showed that stronger prompts could pass the exact gates on other archived cohorts, with lookup costs omitted. This audit uses each measured CPO episode’s paid search and qualification total as that episode’s allowance. It checks how much headroom remains when candidate paths need evidence. [Earlier reachability audit](prompteval-gate-reachability.md) · [Backup comparison](complementary-backup.md) · [Runner](../benchmarks/priced_gate_reachability.py)

The replay uses the published 16 Llama and Mistral panels and 12 Gemma and Flan panels. Each panel has 32 four-cycle episodes. The candidate rosters and case schedule stay fixed. A fresh move needs a strict gain on validation and on separate qualification cases. Leaving the original start also requires nonnegative gain in both qualification halves. An archive move needs the qualification gain. Every path can keep its incumbent and skip a cycle.

| Path model | Lookups charged and available moves |
| --- | --- |
| Full-panel fresh | Charge both complete validation and qualification panels for each fresh move. This funds a direct path when the candidate is already known. It gives no credit for cache reuse. |
| Minimum-proof fresh | Charge only the favorable replies needed for a strict certificate, with optimistic reuse of incumbent misses from earlier validation cases. |
| Minimum-proof archive | Use the same prices and also allow any previously offered prompt to return on a qualification certificate. |
| Uncapped archive | Keep the same moves and qualification gates with enough allowance for every cycle. |
| Any offered prompt | Include the initial prompt and every scheduled challenger. |

On a binary panel of size *n*, the lower bound on the paired gain starts at −*n*. An observed incumbent failure or challenger pass raises that bound by one. Proving a strict gain therefore requires at least *n* + 1 favorable observations. The minimum-proof model charges only those observations and gives every incumbent credit for overlapping misses, even when its path may never have paid for them. The archive model skips the cost of finding and admitting earlier nominees. These relaxations make the minimum-proof reachability optimistic. A full-panel fresh move is a funded comparison with a preselected challenger. It still omits the cost of discovering that challenger.

The audit builds all paths using development cases. It scores the completed prompt sets on held-out cases and classifies each loss against cap-52 GEPA using the earliest path model that can match the control’s score. It reports a zero-cost category when the original start already matches. The ceilings use hindsight and do not measure a deployable selector’s expected performance.

## Results

CPO scored below at least one cap-52 GEPA control in 137 of 896 episodes. Counting each control separately gives 222 losing comparisons. The table assigns each comparison to its earliest matching category.

| First category that matches the GEPA score | Llama and Mistral | Gemma and Flan | Total |
| --- | ---: | ---: | ---: |
| Retain the starting prompt | 63 | 46 | 109 |
| Full-panel fresh path at the measured budget | 63 | 22 | 85 |
| Minimum-proof fresh path only | 0 | 0 | 0 |
| Minimum-proof archive path at the measured budget | 20 | 7 | 27 |
| Uncapped archive path only | 0 | 0 | 0 |
| Any offered prompt only | 0 | 1 | 1 |
| **Total losing comparisons** | **146** | **76** | **222** |

Of the 85 full-panel matches beyond retaining the start, 80 could be funded with one preselected challenger at 40 lookups and five required two moves at 80 lookups. In a separate count, an actual earlier CPO deployment matched GEPA in 100 losing comparisons. That count overlaps the table. The sole comparison that required stepping outside the audited promotion gates was Flan on high-school statistics, seed 47101, against batched GEPA. [Episode-level prices, ceilings, and control traces](priced-gate-reachability-results-v1.json)

The published CPO route still beats retaining the start in aggregate by 107 passes on Llama and Mistral and 31 on Gemma and Flan. The loss audit places most of the observed opportunity in recognizing when to keep an existing prompt or selecting a better fresh finalist using the same allowance. Relaxing the promotion gates would expand the measured ceiling in one losing comparison. The cost of identifying the better choice from paid evidence remains the open question.

The follow-up found that previously paid matched cases favored the final prompt in all 109 losses where retaining the start would have matched GEPA. [Paid-evidence retention replay](paid-start-retention.md)

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two source-export replays matched byte for byte with sockets and DNS blocked. Both reproduced all 84 published CPO and GEPA panel traces and verified containment of the measured CPO finale under the optimistic priced archive model on all 896 episodes. Three focused tests checked one-move-per-cycle semantics, repeated validation cost, archive admission, and the two-half gate. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 13.2 GiB free. The 20.3 MB scratch overlay was removed under the standing LAB exception. [Verification receipt](priced-gate-reachability-verification-v1.json) · [Tests](../tests/unit/test_priced_gate_reachability.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.priced_gate_reachability \
  --execute 6df2d9624908d91155b3982962c9662b19b776788fade6f9b61d646ac2573925 \
  --out NEW_REPORT.json
```
