# Protect the starting prompt during qualification

The matched-cost audit traced 90 of the third-pass route's 167 gross lost holdout passes to episodes where sequential GEPA kept the starting prompt. This follow-up tests whether CPO can preserve strong starts using its original qualification cases and archive slot. It replays both third-observation routes on the three archived cohorts, retaining the original search budget, prompt rosters, and holdout. [Matched-cost loss audit](routed-model-cost-frontier.md) · [Replay runner](../benchmarks/routed_start_protection.py)

## Policies

- **Two at start** requires two net gains in qualification whenever the starting prompt is incumbent.
- **Split departure** uses the original eight qualification cases in two four-case groups. While the start is incumbent, a challenger must gain at least one pass overall and avoid a negative net gain in either group. Fresh qualification uses the CPO paired proof with two families. Archive qualification keeps its incumbent-first order and applies the same criterion.
- **Recall start** gives the starting prompt the existing archive slot in the final cycle if the incumbent differs and that directed pair has yet to be tried.
- **Reserve start for final** also excludes that archive nominee from earlier cycles. Other archive prompts remain eligible. The final check uses the ordinary strict-gain condition, and a rejected check pays for its observed replies before fresh search.
- **Split and recall** and **split and reserve** combine the departure gate with the corresponding archive policy.

## Results

Each cell shows holdout passes / distinct paid search and qualification lookups. The full report includes all 14 route and policy combinations.

| Route and policy | BBH and LMentry | MMLU pilot | MMLU model transfer |
| --- | ---: | ---: | ---: |
| Third pass, ordinary | 3,413 / 39,797 | 22,359 / 33,159 | 12,201 / 50,951 |
| Third pass, two at start | 3,366 / 40,495 | 22,292 / 32,786 | 12,154 / 50,992 |
| Third pass, split departure | 3,416 / 39,563 | 22,359 / 33,003 | 12,201 / 50,485 |
| Third pass, split and recall | 3,417 / 39,624 | 22,356 / 33,018 | 12,201 / 50,484 |
| Third pass, split and reserve | 3,402 / 39,369 | 22,342 / 32,941 | 12,202 / 50,326 |
| Third miss, ordinary | 3,386 / 49,104 | 22,366 / 33,898 | 12,219 / 52,605 |
| Third miss, reserve start for final | 3,377 / 48,812 | 22,351 / 33,726 | 12,228 / 52,569 |
| Third miss, split and reserve | 3,381 / 48,415 | 22,351 / 33,554 | 12,225 / 52,028 |

On the later model splits, splitting qualification on the third-pass route kept the original score and saved 466 lookups. Across the 46 episodes originally lost when GEPA kept its start, the split and archive variants recovered zero net passes on that route. Requiring two gains when leaving the start recovered 84 of those 90 passes, with an aggregate loss of 47 passes across all 512 episodes. The stricter margin reduced both regressions from the start and gains beyond it. [Per-panel results and start-preservation counts](routed-start-protection-results-v1.json)

On the third-miss route, combining split qualification with a final-cycle reserve gained six passes and saved 577 lookups on the later model splits. It returned to the starting prompt in 27 of 144 final nominations. It scored five fewer passes on BBH and LMentry and 15 fewer on the MMLU pilot. On the later splits it led the best affordable fixed GEPA point by 23 passes and scored five below the cheapest fixed point that reached its score, spending 10,155 fewer lookups than the latter. The task-specific GEPA allocation with hindsight scored 61 more passes within its lookup budget.

For that combined setting, 4,096 paired draws resampled holdout cases within subjects, with both models and all episodes carried together. The fixed sequential cap-35 difference had a central 95% range of −45 to +90 passes. Against the two original cap-52 controls the combined policy gained 44 passes against batched GEPA and trailed sequential GEPA by 28. It cleared 10% lookup savings against both. The joint range was −90 to +30 passes. The combined setting and cost comparators were selected for this audit after observing the archived results. Fresh proposal quality and provider spending remain unverified. [Full comparisons and reserves](routed-start-protection-results-v1.json)

## Reproduce

Use pinned GEPA 0.1.4. Preview to get the seal for `model-transfer`, `bbh-lmentry`, or `mmlu`, then execute to a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.routed_start_protection --phase model-transfer
PYTHONHASHSEED=0 python -B -m benchmarks.routed_start_protection \
  --phase model-transfer --execute 3fe5299dcf8a18abac2a7abda7eb2b213e26188ca2cf8276e9aaec970904d6f0 \
  --out NEW_REPORT.json
```

Two source-export replays per cohort matched byte for byte with sockets and DNS blocked. They reproduced 80 ordinary-route CPO traces and 64 fixed GEPA traces with the recorded lookup costs. The two focused tests checked 256 binary qualification panels and critical-case protection. The CLI rejected an incorrect seal. Storage Guard measured 14.0 GiB free. The 14.3 MB scratch overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_routed_start_protection.py)
