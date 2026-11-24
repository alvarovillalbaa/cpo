# Locate the headroom in CPO's language prompt rosters

The [second-case evidence audit](second-case-evidence-transfer.md) found too few eligible promotions for a one-veto policy to beat the bounded opening on discovery. This audit looks earlier. It reproduces the bounded opening and router on the original 2,048 three-cycle episodes, then asks what the same candidate rosters could achieve at the bounded opening's realized lookup budget in each cohort. All replayed moves retain the existing independent qualification proof. [Runner](../benchmarks/language_roster_budget_frontier.py)

## What each comparison can choose

- **Common** chooses one setting for a whole cohort. **By subject** chooses one per subject across its model panels and seeds. **By episode** chooses one setting for all three cycles of each episode.
- **By cycle** can choose a different setting in each cycle, after carrying forward the deployed prompt. These four comparisons use the same menu of quoted uniform and successive-halving settings, the bounded opening, the earlier router, and free retention.
- **Known nominee** adds the ability to reveal a single roster challenger in hindsight. The replay still pays for its one-case or full-panel quoted validation and independent qualification. This measures the value of selecting a challenger before screening the roster.

All five levels select with target holdout grades and realized prices. They are exact optima within their respective measured menus. They include no cost for discovering which setting or challenger to choose. The by-cycle search prunes an arrival at a prompt if another paid path reached the same prompt for less. A second dynamic program pools cost across episodes. The runner directly replays every chosen schedule and checks its score and lookups.

## Results at the bounded opening's budget

Cells show final held-out passes and actual paid lookups. Every choice in a row fits the lookup budget shown in the bounded opening column. The native GEPA upper bound comes from the prior split-safe full-grid menu at that budget. The audit directly replays its affordable native anchors.

| Cohort | Bounded opening | Common | By subject | By episode | By cycle | Known nominee | Task-tuned GEPA upper bound |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,421 | 6,354 / 11,038 | 6,422 / 13,324 | 6,752 / 7,962 | 6,790 / 3,923 | 7,024 / 3,932 | 6,350 |
| Bounded LMentry | 6,338 / 15,636 | 6,529 / 15,335 | 6,575 / 15,450 | 7,127 / 10,671 | 7,237 / 5,035 | 7,471 / 4,111 | 5,931 |
| Bounded MMLU | 7,719 / 6,554 | 7,719 / 6,503 | 7,735 / 5,874 | 7,769 / 1,204 | 7,775 / 565 | 7,825 / 750 | 7,717 |
| Four-case MMLU | 22,369 / 10,591 | 22,389 / 9,624 | 22,412 / 9,821 | 22,450 / 1,062 | 22,450 / 475 | 22,484 / 547 | 22,369 |
| Tie BBH | 2,145 / 12,521 | 2,145 / 12,521 | 2,194 / 12,166 | 2,431 / 5,998 | 2,452 / 2,601 | 2,624 / 2,697 | 2,126 |
| Tie LMentry | 992 / 6,971 | 1,018 / 6,467 | 1,041 / 6,858 | 1,234 / 3,397 | 1,263 / 1,468 | 1,386 / 1,320 | 919 |
| Additional MMLU | 7,398 / 6,354 | 7,398 / 6,354 | 7,408 / 6,229 | 7,427 / 1,082 | 7,427 / 510 | 7,460 / 653 | 7,399 |
| **Pooled** | **53,308 / 72,048** | **53,552 / 67,842** | **53,787 / 69,722** | **55,190 / 31,376** | **55,394 / 14,577** | **56,274 / 14,010** | — |

Selecting by episode adds 1,403 passes over the by-subject schedule and saves 38,346 lookups. Selecting by cycle adds 204 more passes and saves another 16,799 lookups. The cycle-level choice retains without search in 5,389 of 6,144 cycles. Revealing a single nominee adds another 880 passes while keeping the proof gates. The pooled counts are descriptive because cohorts reuse some tasks.

In bounded LMentry, the common winner is eight-challenger uniform search over two validation rows. It gains 191 passes over the bounded opening at 301 fewer lookups. Episode-level selection adds another 598 passes over that common policy and spends 4,664 fewer lookups. In four-case and additional MMLU, choosing by cycle preserves the episode-level score while roughly halving its lookup cost.

The fixed rosters contain large gains under the current proof gates. Most of the schedule-selection headroom appears when the chooser moves from a subject-wide setting to an episode-specific setting. The results establish a target for deciding when to retain and when to search from information available before spending. Live quality and the cost of that decision remain unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a cohort seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.language_roster_budget_frontier \
  --cohort bounded-LMentry \
  --execute 05227d17d809b0e0999d418b781d65dfe411a7152d13956f66a1eaf4f4fd6ec8 \
  --out NEW_REPORT.json
```

[Bounded BBH](language-roster-budget-frontier-bounded-bbh-v1.json) · [Bounded LMentry](language-roster-budget-frontier-bounded-lmentry-v1.json) · [Bounded MMLU](language-roster-budget-frontier-bounded-mmlu-v1.json) · [Four-case MMLU](language-roster-budget-frontier-four-case-mmlu-v1.json) · [Tie BBH](language-roster-budget-frontier-tie-bbh-v1.json) · [Tie LMentry](language-roster-budget-frontier-tie-lmentry-v1.json) · [Additional MMLU](language-roster-budget-frontier-additional-mmlu-v1.json)

Twenty-nine targeted tests passed, including exhaustive checks of a pooled lookup frontier and a two-cycle replay graph. Duplicate replays matched byte for byte with DNS and outbound sockets blocked. Both baseline trajectories reproduced and no provider requests were made. Storage Guard measured 9.7 GiB free. The source export, dependency overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_language_roster_budget_frontier.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
