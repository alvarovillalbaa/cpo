# Early screening and backup finalists

The balanced-six search ranks up to six challengers on two cases before validating the finalists. This replay tests how much of that screen is necessary and when a second finalist is worth validating. It retains the archived proposals, validation cases and cap, archive rules, and eight-case qualification. The race runs either in every fresh search or only after two incumbent misses. [Prior validation-bound replay](finalist-bound-replay.md)

## Screening and validation

The screen visits challengers in proposal order. Once the shortlist is full, it can stop reading a challenger whose observed passes plus unread cases cannot exceed the lowest admitted score. A tied score goes to the earlier proposal. Once the lowest admitted score reaches the number of probes, the screen can skip every remaining challenger by the same argument. The selector reuses the probe replies it already paid for.

The replay also validates only the top challenger, either alone or with a backup. The backup policy opens the two-finalist race if the top challenger fails to improve on the incumbent under the original validation and critical-case rules. It shares the reply ledger and uses the original two-finalist cap. The bounded validation variant applies the earlier exact score bounds after early screening. [Replay implementation](../benchmarks/finalist_screen_budget.py)

## Archived outcomes

Each cell shows holdout passes / distinct search and qualification lookups. The full two-finalist column uses the original screen and validation.

| Cohort and policy | Full two finalists | Early screen and validation bounds | Early screen, one finalist | Early screen, try backup |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry, always wide | 3,467 / 66,768 | 3,467 / 63,068 | 3,431 / 50,036 | 3,481 / 59,032 |
| BBH and LMentry, two-miss routing | 3,429 / 55,332 | 3,429 / 53,002 | 3,393 / 45,666 | 3,419 / 50,448 |
| MMLU pilot, always wide | 22,464 / 56,591 | 22,464 / 51,107 | 22,431 / 41,440 | 22,458 / 48,774 |
| MMLU pilot, two-miss routing | 22,390 / 37,902 | 22,390 / 36,596 | 22,377 / 33,840 | 22,391 / 35,895 |
| MMLU model transfer, always wide | 12,253 / 80,684 | 12,253 / 73,015 | 12,215 / 58,754 | 12,251 / 69,527 |
| MMLU model transfer, two-miss routing | 12,223 / 57,283 | 12,223 / 55,371 | 12,201 / 50,948 | 12,223 / 54,166 |

Early screening alone saved **14,905** always-wide lookups and **4,071** routed lookups while preserving every two-finalist decision. Combined with validation bounds, savings reached **16,853** and **5,548**, respectively. Early screening alone never increased paid search in any paired episode for either shortlist size. [Results and per-panel traces](finalist-screen-budget-results-v1.json)

On the MMLU pilot, both routed one-finalist policies exceeded both archived GEPA references in holdout passes and used fewer lookups. On the later model splits, the routed backup gained 42 passes and used 3,651 fewer lookups (6.3%) against batched GEPA. It was 30 passes behind sequential GEPA. The always-wide policy with early screening and validation bounds tied sequential GEPA's 12,253 passes and used 10,235 fewer lookups (12.3%), with a higher cost than batched GEPA. On BBH and LMentry the always-wide backup improved on sequential GEPA by 24 passes and saved 6,220 lookups, with a higher cost than batched GEPA. These outcomes support measuring the policies prospectively. Fresh-model superiority and provider spend remain unverified.

## Reproduce

Use GEPA 0.1.4. Preview each phase for its seal. The other phases are `bbh-lmentry` and `mmlu`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.finalist_screen_budget --phase model-transfer
PYTHONHASHSEED=0 python -B -m benchmarks.finalist_screen_budget \
  --phase model-transfer --execute ffade85fe6ea259874e73da4a94077f6c835ba41dde97e8e330c8b8a50b7d2b8 \
  --out NEW_REPORT.json
```

Two source-export replays per cohort matched byte for byte with sockets and DNS blocked. All 80 original CPO panel traces reproduced. The three exact comparisons preserved the decisions and complete qualification trace across 30,720 paired cycle checks. The focused tests checked both shortlist sizes on all 4,096 binary probe matrices and exercised critical-case protection, lookup accounting, and backup validation. The CLI rejected an incorrect seal. Storage Guard measured 15.8 GiB free. The 12.4 MB scratch overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_finalist_screen_budget.py)
