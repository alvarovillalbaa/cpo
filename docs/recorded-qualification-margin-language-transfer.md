# Transfer two-gain qualification to BBH and LMentry

The two-gain screen improved CPO on both archived MMLU cohorts. This replay freezes the same cap-13 complete-panel-reserve screen and tests one- and two-gain qualification on 44 archived panels across 14 BBH tasks and eight LMentry tasks. The panels pair the Airoboros-13B and Nous-Hermes-13B checkpoints. The earlier source study used these matrices for a four-cycle comparison. This replay uses the frozen single-cycle MMLU schedule with eight challengers, six validation cases, four independent qualification cases, and 32 seeds per model panel. [MMLU result](recorded-matched-qualification-margin.md) · [Archived language panels](qualification-order-transfer.md)

The two CPO variants share each start, roster, paid screen, and nominee. Both native GEPA modes can use either qualification rule at every cap from 6 to 180. Each paired draw resamples held-out cases within tasks, keeps both model panels and all seeds together, and reselects the strongest affordable native control or retained starts. Budget includes search and qualification. The gate requires a positive point margin and a nonnegative lower paired bound. [Replay runner](../benchmarks/recorded_qualification_margin_language_transfer.py)

| Cohort | One-gain CPO passes / lookups | Two-gain CPO passes / lookups | Effect of requiring two gains and paired 95% range |
| --- | ---: | ---: | ---: |
| BBH | 9,363 / 12,567 | 8,953 / 12,402 | −410, −470 to −353 |
| LMentry | 5,166 / 7,105 | 4,826 / 7,051 | −340, −382 to −299 |

The stronger qualification vetoed 90 of the 144 BBH promotions and 50 of the 115 LMentry promotions. It saved 219 qualification lookups and lost 750 held-out passes in total. The one-gain screen cleared the fixed-setting GEPA gate on both cohorts. Its paired margin was +450 on BBH with a 95% range of +390 to +513, and +583 on LMentry with a range of +517 to +650. The strongest affordable control on both was sequential GEPA at cap 16 with one-gain qualification. The two-gain screen remained ahead of that control on LMentry by 243 passes, with a paired range of +193 to +295. Its BBH range crossed zero.

The MMLU improvement did not carry over to these families. The archived results favor one-gain qualification for the BBH and LMentry screen at this cap. The experiments reuse recorded replies, and fresh-model performance remains unverified. [Complete cost curves, paired comparisons, and panel results](recorded-qualification-margin-language-transfer-results-v1.json)

Two follow-up rules used paid validation grades to choose the margin. Neither selected the stronger fixed margin across the MMLU and language cohorts. [Paid qualification margin selection](recorded-paid-qualification-margin-route.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_qualification_margin_language_transfer
python -B -m benchmarks.recorded_qualification_margin_language_transfer \
  --execute ccbe1ac596beaabf364b43b2ab54e895d34d12e3c1fbc6e0a6c1503e8d103f78 \
  --out NEW_REPORT.json
```

Preflight caught a mismatched parent receipt reference and the archive’s nested template identities. The final runner binds the MMLU comparison receipt and validates the complete ordered template and case axes before scoring. Two clean-export runs with DNS and sockets blocked matched byte for byte at SHA-256 `48fbb94ac5e99fa020a867d3642bba2c35f4456d2ad14e9dbad5795a9ad345be`. All 45 targeted tests passed. The replay checked 24,366 native search paths under both rules. A direct audit checked each possible qualification-case omission across all 1,408 trials and replayed the selected controls. The CLI rejected the preceding seal. Storage Guard measured 0.7 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Regression tests](../tests/unit/test_recorded_qualification_margin_language_transfer.py)
