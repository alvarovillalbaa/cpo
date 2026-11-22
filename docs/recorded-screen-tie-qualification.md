# Admit a witnessed validation tie to independent qualification

The coverage audit found more promising archived prompts after strict qualification than after both strict gates. This replay preserves the complete-panel screen and every strict validation nominee. When the screen finds none, it can nominate a challenger that ties the incumbent on validation, preserves its critical passes, and has a paid pass on a case the incumbent missed. The same independent qualification still requires a strict gain. [Coverage audit](recorded-screen-coverage-ceiling.md) · [Witnessed-tie rule](recorded-math-validation-ties.md)

One policy uses only replies already paid for. The other can buy up to two further replies when the screened challenger can still finish with an exact tie. Both retain the original cap of 13 search lookups. The 960 trials and held-out cases come from the previous MMLU transfer. No new cases were enrolled. The gate requires a positive observed margin and a nonnegative lower paired bound against the best affordable fixed CPO setting, native GEPA setting, published screen, or retained start. Each paired draw reselects that control at the candidate’s realized cost. [Replay runner](../benchmarks/recorded_screen_tie_qualification.py)

| Policy | Tie nominees / promotions | Held-out passes | Paid lookups | Margin and paired 95% range |
| --- | ---: | ---: | ---: | ---: |
| Strict complete-panel screen | — | 56,079 | 9,596 | — |
| Already-paid tie | 14 / 4 | 56,079 | 9,670 | 0, −29 to +10 |
| Up to two reads to finish a tie | 30 / 6 | 56,080 | 9,782 | +1, −30 to +13 |

The two-read variant added one net held-out pass and cost 186 more lookups than the strict screen. Its six promotions gained four passes and lost three. The already-paid variant gained and lost three passes. The strict screen ranked first among the affordable controls for both variants. Sequential GEPA at cap 16 scored 56,068 with 9,320 lookups. Neither tie variant cleared the joint gate. The experiment leaves fresh-model performance unverified. [Full results and per-panel traces](recorded-screen-tie-qualification-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_screen_tie_qualification
python -B -m benchmarks.recorded_screen_tie_qualification \
  --execute 7c3c762f6dc549a8710d0e8d6e4194ac9be9ef7015a9ac4f6e7ba77bf532d852 \
  --out NEW_REPORT.json
```

The targeted tests exposed that the shared adapter forwards the prompt and drops its tie flag. The benchmark records ties at nomination and counts promotions after independent qualification. All 40 targeted tests passed. Two clean-export replays with DNS and sockets blocked matched byte for byte at SHA-256 `3b461caa5b365206d9758179a83e381ac51c4d897b7dd3e971dd75854763809c`. Direct checks verified 1,920 paths and the selected GEPA control. The CLI rejected the predecessor seal. Storage Guard measured 3.1 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Regression tests](../tests/unit/test_recorded_screen_tie_qualification.py)
