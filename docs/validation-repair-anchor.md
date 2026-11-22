# Compare shared validation on a case the incumbent missed

The certified wide policy reduced validation lookups while preserving every decision. It still trailed the split-safe GEPA score on both MMLU cohorts. This replay tests a different allocation of validation lookups. It opens on the first observed incumbent miss across the six scheduled validation cases. If the incumbent passes all six, the policy keeps it without scoring challengers. [Previous comparison](certified-shared-validation.md) · [Replay runner](../benchmarks/validation_repair_anchor.py)

- **Single repair** selects the first challenger that passes the witness case in the original roster order.
- **Four-repair cut** collects up to four challengers that pass the witness. When the cap can cover the entire follow-up, it favors the first to pass a second shared case. It reuses an incumbent pass from the witness search when available. The earliest repair wins when all challengers fail the second case or when the follow-up cannot be funded.

Both policies use the same 19-lookup search cap, fixed roster, and original independent precheck and qualification. Every nominated challenger needs a paid pass on the incumbent miss. Every deployment still needs the exact independent gain. The comparison covers the same 134 model panels and 32 schedules at one and two qualification gains. The two MMLU cohorts are primary. The BBH and LMentry cohorts check how the policy travels to other tasks and checkpoints. [Fixed inputs and checked paths](validation-repair-anchor-results-v1.json)

## MMLU results

Each entry gives held-out passes and total paid lookups. The same published split-safe GEPA setting attains the prior ceiling at both qualification margins for each MMLU cohort. GEPA settings were selected per subject using the archived holdout, so they are hindsight comparators. The replay independently reproduced each setting's score and cost. [Split-safe GEPA settings](shared-validation-split-safe-transfer.md)

| Cohort and qualification gain | Certified wide | Single repair | Four-repair cut | Published GEPA attainer |
| --- | ---: | ---: | ---: | ---: |
| Earlier MMLU, one | 26,642 / 14,732 | 26,635 / 9,061 | 26,637 / 10,145 | 26,655 / 8,574 |
| Disjoint MMLU, one | 56,034 / 13,942 | 56,080 / 9,195 | 56,081 / 10,042 | 56,089 / 6,814 |
| Earlier MMLU, two | 26,632 / 9,931 | 26,633 / 6,841 | 26,633 / 7,512 | 26,655 / 8,574 |
| Disjoint MMLU, two | 56,084 / 8,977 | 56,091 / 6,703 | 56,090 / 7,227 | 56,089 / 6,814 |

The primary four-repair policy missed the one-gain gate in both cohorts. Its paired pass ranges against GEPA were −45 to +9 on earlier MMLU and −54 to +40 on disjoint MMLU. At two gains on disjoint MMLU, single repair scored two more passes and used 111 fewer lookups than the published attainer. The paired 95% range was −22 to +27 passes, holding the GEPA settings fixed and resampling held-out cases within subject. That attainer is outside single repair's budget. Its score still bounds the affordable GEPA ceiling from above. The report gives separate affordability bounds for each comparison.

## Which decisions account for the gap?

On disjoint MMLU at one gain, certified wide and GEPA agreed on the deployed prompt in 859 of 960 trials. In 96 other trials certified wide promoted and GEPA retained the start, gaining 66 net passes for GEPA in that group. Certified wide led by 15 passes in the four trials where both promoted different prompts. One rejected CPO proof accounted for GEPA's remaining four passes. Across all trials GEPA led by 55 passes.

On earlier MMLU at one gain, the pattern differed. Certified wide gained seven passes on the 114 trials where it promoted and GEPA retained. GEPA gained 10 passes on three rejected CPO proofs, five where CPO found no nominee, and five where the methods promoted different challengers. The qualification precheck did not account for any deployment difference on either cohort.

The four-repair cut improved by 47 passes against certified wide on disjoint MMLU at one gain. In the 70 trials where only certified wide promoted, the four-repair cut gained 59 passes. On earlier MMLU, the corresponding 85 trials cost it six passes. Fewer promotions helped in one cohort and gave up useful improvements in the other.

The four-repair cut also led the affordable GEPA upper bound by 80 passes on transferred LMentry checkpoints and by 36 on ends-with-word at one gain. It lost 46–359 passes against certified wide on the three BBH cohorts and lost 482 on original LMentry. Witness-first search remains a benchmark experiment. Fresh-model performance remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.validation_repair_anchor
PYTHONHASHSEED=0 python -B -m benchmarks.validation_repair_anchor \
  --execute 67cd20e8e72c4b5c5d6d2e6bdc381fa9aa515f648fdbd4337632d8c872b0581f \
  --out NEW_REPORT.json
```

Two DNS- and socket-blocked replays from a clean source export produced byte-identical reports at SHA-256 `b4412eb9955fed5675855af7a8c98022c8e688c8fb4cf57b005425a3bffdf6e0`. The replay reproduced all certified-wide traces and both MMLU GEPA settings. Fourteen targeted tests passed. Storage Guard measured 2.2 GiB free. The source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Focused tests](../tests/unit/test_validation_repair_anchor.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
