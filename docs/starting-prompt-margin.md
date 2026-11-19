# Require more evidence to leave the starting prompt

Seeded CPO used fewer paid lookups than batched GEPA on the eight new MMLU panels and finished 25 holdout passes behind. Nutrition contributed 21 of those net lost passes. This follow-up replays both measured paths to locate losses and tests a larger qualification margin while the starting prompt is incumbent. [Independent transfer](independent-mmlu-transfer.md)

## Where the losses occurred

Seeded CPO lost 44 of 256 episodes, won 41, and tied 171 against batched GEPA. The losses totalled 116 gross passes before offsetting wins. Each losing episode is classified by the recorded path and, where necessary, the exact archived outcomes on the cycle where the GEPA winner was offered.

| Reason | Episodes | Gross lost passes |
| --- | ---: | ---: |
| GEPA retained the starting prompt | 18 | 48 |
| CPO missed a winner that would pass both strict gates on its offered cycle | 12 | 29 |
| The winner had no positive validation gain against CPO's incumbent | 8 | 21 |
| The winner had a positive validation gain and no positive qualification gain | 5 | 17 |
| An archive promotion skipped the fresh pool containing the winner | 1 | 1 |

Nutrition accounted for 16 losing episodes. GEPA retained the start in nine of them, contributing 20 of the 44 gross lost nutrition passes. A different winner reached neither fresh nor archive qualification on CPO's measured path in any losing episode. The post-run check uses archived outcomes to identify opportunities the selector did not observe. It does not establish that a different policy could have found all 12 strict-gain winners within the paid cap.

## Qualification margins

The seeded control requires a one-pass gain. The two start-only methods require two or three passes whenever the starting prompt is incumbent, and one otherwise. The all-two method requires two passes on every comparison. The same thresholds apply to fresh and archive qualification. An archive comparison still reads the incumbent first and stops once the paid prefix proves or rules out the required gain. The variants keep the original proposal schedules, validation, qualification rows, archive eligibility, and combined lookup cap. [Runner](../benchmarks/starting_prompt_margin.py)

| Required gain | New MMLU passes / paid lookups | Both GEPA gates / 8 | Earlier three cohorts passes / paid lookups | Both GEPA gates / 32 |
| --- | ---: | ---: | ---: | ---: |
| One pass throughout | 8,971 / 21,477 | 2 | 21,023 / 101,034 | 15 |
| Two at the start | 8,956 / 21,465 | 2 | 21,009 / 101,865 | 13 |
| Three at the start | 8,917 / 21,039 | 1 | 20,953 / 100,594 | 13 |
| Two throughout | 8,951 / 21,514 | 2 | 21,040 / 102,212 | 14 |

Requiring two passes at the start gained nine on Falcon nutrition. It lost 14 on Gemma nutrition and 15 across the new panels as a whole. Requiring three left the final prompt at the start in 253 of 256 episodes and finished one pass below the retain-start arm. The all-two policy gained 17 passes on the earlier cohorts for 1,178 extra lookups and lost 20 passes on the new MMLU panels. The one-pass gate remains the default.

The replays reproduced all 40 published seeded CPO traces and the eight batched GEPA traces used for attribution. Two executions per phase produced byte-identical reports. The archive proof also matched the full gain decision on every three-case binary pair at both higher margins. These are retrospective results on recorded prompt pools. Fresh-model quality and provider costs remain unverified. [Sealed results and per-episode attribution](starting-prompt-margin-results-v1.json)

A follow-up compared broader screens against the same controls and checked which of the 12 strict-gain misses they recovered. [Budgeted second probe](budgeted-second-probe.md)

A separate replay compared the fixed margin with gates that distinguish paired wins and losses at the same net gain. The paired rules yielded mixed results across all five archived cohorts. [Paired promotion evidence](paired-promotion-evidence.md)

## Reproduce

Use GEPA 0.1.4. Preview the phase seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. Phases are `independent`, `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.starting_prompt_margin --phase independent
```
