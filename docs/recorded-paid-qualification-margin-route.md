# Choose a qualification margin from paid validation

Two-gain qualification improved the archived MMLU screen and reduced scores on BBH and LMentry. This replay tests whether paid validation can identify when to require two gains. One rule uses two gains when a nominee has a paid loss on a case the incumbent passed. The other uses two gains when the incumbent passed at least four of six validation cases. Both use one gain otherwise. Neither rule uses a benchmark name or a qualification result to choose its margin. [Matched MMLU comparison](recorded-matched-qualification-margin.md) · [BBH and LMentry transfer](recorded-qualification-margin-language-transfer.md)

The cap-13 screen, nominee, incumbent qualification prefix, case assignments, and independent proof remain the same as in the fixed-margin experiments. The replay reconstructs the two published fixed margins and verifies that every routed trial reproduces its chosen proof path. The 3,264 trials across 102 archived model panels already appeared in the source studies. Paired case resampling compares each rule with the fixed margins within each cohort. [Replay runner](../benchmarks/recorded_paid_qualification_margin_route.py)

| Cohort | Paid-regression rule, pass change and paired 95% range vs one gain | Four-pass rule, pass change and paired 95% range vs one gain | Four-pass rule, lookups saved vs one gain |
| --- | ---: | ---: | ---: |
| Earlier MMLU | +3, 0 to +6 | +4, −12 to +19 | 99 |
| Disjoint MMLU transfer | 0, 0 to 0 | +9, −9 to +26 | 104 |
| BBH | −25, −44 to −6 | −14, −24 to −4 | 16 |
| LMentry | +1, −7 to +10 | −8, −15 to −1 | 7 |

The paid-regression rule selected two gains twice on the earlier MMLU cohort and never on the MMLU transfer. The four-pass rule recovered nine of the 15 passes gained by fixed two-gain qualification on the MMLU transfer. It still used 97 more lookups and scored six fewer passes than fixed two-gain qualification there. On BBH and LMentry, its ranges were below the fixed one-gain screen. Neither tested signal consistently selected the stronger fixed margin across cohorts.

The receipt gives the strongest measured affordable GEPA point for each routed policy. These are descriptive archive reference points. The fixed-margin comparisons in the table use paired uncertainty ranges. Fresh-model performance remains unverified. [Full results and panel decision traces](recorded-paid-qualification-margin-route-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_paid_qualification_margin_route
python -B -m benchmarks.recorded_paid_qualification_margin_route \
  --execute ed6526c44b3f547863d941236f02a059976c03a4e09840f5ae8731140d24d703 \
  --out NEW_REPORT.json
```

Two clean-export replays with DNS and sockets blocked matched byte for byte at SHA-256 `81f92caf936a3b91095d75773a72103875ee2cc9eb909dc7e5a6282bfe7febf2`. All 47 targeted tests passed. An independent audit reconstructed the paid signals and resulting deployments across 6,528 paths and replayed the selected native controls. The CLI rejected a predecessor seal. Storage Guard measured 3.0 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Regression tests](../tests/unit/test_recorded_paid_qualification_margin_route.py)
