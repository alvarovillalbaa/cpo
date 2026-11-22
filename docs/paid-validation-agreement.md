# Check for a paid repair before qualifying a validation finalist

An earlier replay found that qualified promotions hurt certified-wide CPO on disjoint MMLU and helped it on earlier MMLU. This experiment keeps the certified-wide finalist and asks whether its paid validation grades show a repair. A repair requires the finalist to pass a case the incumbent failed. Under the nonloss screen, a finalist without such a repair has the same grades as the incumbent on their shared validation cases. [Prior MMLU attribution](validation-repair-anchor.md) · [Replay runner](../benchmarks/paid_validation_agreement.py)

- **Require a paid repair** blocks qualification when those grades contain no repair.
- **Seek a repair in the spare cap** uses the unspent part of the 19-lookup search cap on unused validation cases in their original order. It checks the incumbent first, reserves enough for the pair, and only reads the finalist after an incumbent miss. It admits the finalist at the first observed repair.

The experiment reuses the same exact independent qualification path whenever it admits the finalist. Both variants leave critical validation on the original strict screen. The eight archived cohorts keep their existing starts, fixed rosters, and disjoint case assignments. Both qualification margins are measured. The primary comparison is the spare-cap rule at one gain on both MMLU cohorts. [Sealed results](paid-validation-agreement-results-v1.json)

## Results

Each entry gives held-out passes and paid lookups. The GEPA settings reproduce the published subject-tuned split-safe ceilings and remain affordable in each cell. [Split-safe comparator](shared-validation-split-safe-transfer.md)

| Cohort and independent gain | Certified wide | Require a paid repair | Seek a repair in the spare cap | Split-safe GEPA |
| --- | ---: | ---: | ---: | ---: |
| Earlier MMLU, one | 26,642 / 14,732 | 26,646 / 12,569 | 26,639 / 14,579 | 26,655 / 8,574 |
| Disjoint MMLU, one | 56,034 / 13,942 | 56,095 / 11,741 | 56,083 / 13,822 | 56,089 / 6,814 |
| Earlier MMLU, two | 26,632 / 9,931 | 26,633 / 9,167 | 26,636 / 10,247 | 26,655 / 8,574 |
| Disjoint MMLU, two | 56,084 / 8,977 | 56,090 / 8,289 | 56,090 / 9,379 | 56,089 / 6,814 |

At one gain, requiring a paid repair on disjoint MMLU added 61 passes versus certified wide, with a paired 95% range of +10 to +112. It saved 2,201 lookups. It led GEPA by six passes, with a range of −37 to +49 and 4,927 more lookups. The earlier MMLU comparison added four passes versus certified wide, with a range of −34 to +41, and remained nine passes behind GEPA. The ranges resample cases within subject with the GEPA settings fixed.

The spare-cap policy missed the primary gate on both MMLU cohorts. At one gain its extra validation cost was 1,728 lookups on earlier MMLU and 1,941 on disjoint MMLU. Compared with requiring a paid repair, it added 12 and six promotions respectively. Those additional deployments lost seven and 12 net held-out passes. The original shared validation grades distinguished harmful and useful promotions more clearly on disjoint MMLU than the additional witness search did.

At one gain on original BBH and LMentry, requiring a paid repair lost 100 and 116 passes versus certified wide. The guarded runs still beat the prior GEPA upper bound in those two cohorts at their lower budgets. Finalists that tied the incumbent case for case on paid validation accounted for 75 original BBH and 34 original LMentry promotions. Removing those promotions lost held-out passes. The policies remain benchmark-only and fresh-model performance is unverified.

## Reproduce offline

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.paid_validation_agreement
PYTHONHASHSEED=0 python -B -m benchmarks.paid_validation_agreement \
  --execute 0de54dc2a49e7149fc4e1042697703bed466e86f6ed75916d33eef41ae2f5fd8 \
  --out NEW_REPORT.json
```

Two clean-source replays with DNS and outbound sockets blocked produced identical reports at SHA-256 `1661ef5380888d37fa2aff1c339d3ba1541899591dd895aadac0e46067055ebe`. Both reproduced all 268 certified-wide panel-by-margin traces and the MMLU GEPA settings. Nineteen targeted tests passed. A separate enumeration checked both witness rules against direct budget and admission calculations in 12,288 combinations of binary grades, caps, and policies. Storage Guard measured 2.2 GiB free at preflight. The source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Focused tests](../tests/unit/test_paid_validation_agreement.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
