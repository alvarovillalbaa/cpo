# Stress routed repair under incomplete and redundant features

The routed repair previously passed all 90 scripted typed panels with the full input feature mapping. This replay uses 60 new panels and compares the installed API’s routing rule with two changes. Deduplication gives identical categorical partitions one vote, even when two columns use different labels. Coverage gives each positively weighted feature value one vote per probe batch, so the next probe can cover a different suspected miss. The combined policy is primary. [Earlier clean-feature results](opening-repair-probe-routing.md) · [Comparison runner](../benchmarks/opening_probe_robustness.py)

Every panel runs with clean features, with the last input field removed from the router’s view, and with six copies of a three-category metadata column added. The added column is derived from the case ID without using outcomes. The evaluator and proposer still see the original cases in all three modes. The alternatives use the same opening, 56-lookup search cap, two later repair stages, and independent qualification. The control holds all cases, prompts, and scoring rules fixed across feature modes. Each holdout panel has 18 cases.

| Method | Clean passes / calls | Missing field passes / calls | Redundant metadata passes / calls |
| --- | ---: | ---: | ---: |
| Routed repair | 1,062 / 3,773 | 1,013 / 3,716 | 1,056 / 3,790 |
| Deduplicated features | 1,062 / 3,773 | 1,013 / 3,716 | 1,062 / 3,773 |
| Distinct feature coverage | 1,062 / 3,803 | 1,013 / 3,715 | 1,062 / 3,803 |
| Deduplication and coverage | 1,062 / 3,803 | 1,013 / 3,715 | 1,062 / 3,803 |
| Sequential GEPA | 1,024 / 4,044 | 1,024 / 4,044 | 1,024 / 4,044 |
| Batched GEPA | 807 / 4,225 | 807 / 4,225 | 807 / 4,225 |

Deduplication recovered all six passes lost to redundant metadata and saved 17 calls. Coverage added 30 calls in clean mode while preserving the same passes. With the field missing, coverage and ordinary routing tied in aggregate, but coverage lost ten matched critical passes on one service panel. Both selected probes passed on training, so the cycle spent no further repair stage. On seven of the eight missing-field panels where the combined policy trailed sequential GEPA, the first two probes passed while the accepted opening still had validation misses.

On `stock/two-missing/60373`, full validation found zero exact gain over the starting prompt in every family. The opening screen ended the cycle before any diagnostic training probe. That was the only clean panel where the combined policy trailed sequential GEPA. The aggregate clean lead still lost six matched critical cases against that control. The combined policy failed the adoption gate, which requires preserving clean paired passes, clearing both GEPA gates in every feature mode, and gaining at least eight passes at equal or lower cost or saving at least 10% at equal or higher accuracy in each stress mode. The published routed repair remains the reference. [Sealed results and paired losses](opening-probe-robustness-results-v1.json)

## Reproduce offline

Use GEPA 0.1.4, the source at commit `5bfa5067c2b0ddeb63c2ffc698a141b7d8bf41a7`, and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_probe_robustness
PYTHONHASHSEED=0 python -B -m benchmarks.opening_probe_robustness \
  --execute 9376a7a1b6f4ce48b8b93e824adcea6be04306588bc300a82fe5191d186e1de4 \
  --out NEW_REPORT.json
```

Two offline replays matched byte for byte. Each replay ran 60 scripted panels under three feature modes, with 120 native GEPA paths shared across modes. Eleven focused tests passed. The runner rejected an altered seal and preserved an existing output. Storage Guard measured 4.6 GiB free. The 29.3 MB scratch export was removed under the standing LAB exception. Live performance on incomplete or redundant features remains unmeasured. [Verification receipt](opening-probe-robustness-verification-v1.json)

The follow-up let a field-score gain unlock repair context and allowed unused probes after a passing batch. It cleared the clean and redundant-feature transfer gates and still missed the critical-case gate with a field hidden. [Stall recovery comparison](opening-stall-recovery.md)
