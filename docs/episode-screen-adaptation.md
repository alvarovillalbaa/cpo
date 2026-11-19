# Widen the search after a stalled cycle

Task-level tuning saved some paid lookups but lost holdout passes. This experiment tests whether earlier search outcomes on the same incumbent can tell CPO when to use its bounded two-read screen. [Task-level tuning](task-budget-selection.md)

The first fresh search uses deferred first-gain. Three rules can widen a later fresh search.

- **After an empty search.** Use bounded two-reads after a fresh search nominates no finalist. The rule can fire again after another empty search.
- **Once after two empty searches.** Widen once per episode after two consecutive fresh searches nominate no finalist.
- **Once after two searches without a promotion.** Widen once per episode after two consecutive fresh searches keep the incumbent, including when a finalist reaches qualification and fails.

An incumbent change clears the history. If the recency archive promotes a prompt, that cycle performs no fresh search. Every policy uses the same candidate schedules, archive rules, 52-lookup cap, and separate qualification rows. Only prior cycle outcomes can change the screen. The holdout is scored after the four-cycle episode. [Replay runner](../benchmarks/episode_screen_adaptation.py)

The replay uses the 16 archived PromptEval tasks across 32 model-task panels with 32 seeds per panel. It measures paid validation lookups after exact cache reuse and paid qualification lookups after early stopping. Both static CPO screens must reproduce their published callback traces, costs, and scores on every panel. The two GEPA controls can each reinvest cached lookups within the paid cap. A panel clears a comparison gate if CPO matches or improves the control's score within its paid cost and either gains a pass or saves at least 10% at equal accuracy. [Static screens](fixed-pool-cycle-replay-results-v1.json) · [GEPA controls](gepa-paid-cap-transfer-results-v1.json)

## Results

| Screen | Holdout passes | Paid lookups | Episodes widened / 1,024 | Panels clearing both GEPA gates / 32 |
| --- | ---: | ---: | ---: | ---: |
| Deferred first-gain | 21,023 | 101,034 | 0 | 15 |
| Bounded two-reads | 20,963 | 107,423 | 1,024 | 12 |
| After an empty search | 20,981 | 103,468 | 635 | 14 |
| Once after two empty searches | 21,020 | 101,825 | 259 | 16 |
| Once after two searches without a promotion | 20,999 | 102,176 | 707 | 13 |

Waiting for two empty searches gained seven passes on MMLU and lost ten across the two BBH and LMentry phases. It improved nine episodes and regressed six, with 1,009 ties. It cleared both comparison gates on one additional panel at the cost of 791 more paid lookups and three fewer aggregate passes. Deferred first-gain remains the default.

The two GEPA controls finished at 20,992 passes with 170,448 paid lookups for sequential search and 20,746 passes with 123,137 for batched search. These comparisons use archived fixed prompt pools. The replay exercises a rule that could run online, while its measured gains and losses are retrospective. Two independent offline executions of each phase produced byte-identical reports. [Sealed results and paired episode counts](episode-screen-adaptation-results-v1.json)

A follow-up keeps the first-gain screen and uses earlier paid replies to choose the case it probes. [Cached witness replay](cached-miss-witness.md)

## Reproduce

Preview each phase with GEPA 0.1.4. Add `--execute PLAN_SHA256 --out NEW_REPORT.json` to replay it. Supported phases are `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.episode_screen_adaptation --phase mmlu
```
