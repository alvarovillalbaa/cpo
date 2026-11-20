# Resume narrow search after the first finalist fails

Changing the opening screening case failed to transfer. This replay preserves the original narrow search until its first finalist fails exact validation. It then asks whether the remaining budget can fund a useful retry. The original wide search, archive preflight, fresh qualification, and per-cycle cap stay in place. [Late miss transfer](late-miss-transfer.md) · [Original narrow search](../cpo/lazy_incumbent.py)

The retry continues with candidates after the rejected finalist in proposal order. It can attempt at most one more validation proof. Before screening any further candidate, the policy reserves the full remaining cost of that proof, crediting incumbent replies already in the ledger. The **same-witness** arm keeps the original screening case. The **shared-miss** arm switches to the first different case that both the incumbent and the rejected finalist were observed to miss, if the ledger contains one. Both arms require a strict validation gain and then pass the challenger to the original independent qualification. [Runner](../benchmarks/funded_finalist_retry.py)

The three cohorts contain 44 archived model and subject panels. Each panel uses its original 32 four-cycle schedules. The replay verifies the original CPO route and both cap-52 GEPA controls against the published traces and costs. Its paired intervals resample the original holdout cases within each subject, retaining both models and all episodes in each draw. The primary arm needs at least 10% fewer paid lookups and a nonnegative lower endpoint for the joint central 95% paired accuracy range against both GEPA controls. [Source comparison](family-qualification-order.md)

## Results

Each cell gives total holdout passes and paid lookups.

| Method | Llama and Mistral | Gemma and Flan | Mixtral and Falcon |
| --- | ---: | ---: | ---: |
| Original CPO route | 17,724 / 49,330 | 17,435 / 35,496 | 29,616 / 46,981 |
| Same-witness retry | 17,729 / 51,777 | 17,436 / 37,352 | 29,610 / 49,489 |
| Shared-miss retry | 17,720 / 51,295 | 17,442 / 36,916 | 29,615 / 49,210 |
| Batched GEPA, cap 52 | 17,694 / 57,271 | 17,422 / 40,184 | 29,600 / 53,024 |
| Sequential GEPA, cap 52 | 17,721 / 81,537 | 17,409 / 60,951 | 29,625 / 77,567 |

The same-witness retry found 134 additional validation winners across 429 retry screens. It tied the original route in total holdout passes and used 6,811 extra lookups. The shared-miss retry found 82 additional validation winners across 430 retry screens. It gained two net holdout passes and used 5,614 extra lookups. The paired ranges against the original route include zero on all three cohorts for both policies. [Per-panel results and ranges](funded-finalist-retry-results-v1.json)

The shared-miss arm saved 10.4%, 8.1%, and 7.2% of paid lookups against batched GEPA. Its joint paired accuracy ranges against both GEPA controls were −59 to +55, −29 to +68, and −86 to +60 passes. Neither retry cleared the combined gate on any cohort. The existing CPO selector remains in place. Fresh-model comparisons remain pending.

The follow-up tested requiring a validation gain beyond the screening case. [Validation beyond the first probe](independent-witness-validation.md)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path. Preview the design to obtain the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.funded_finalist_retry
PYTHONHASHSEED=0 python -B -m benchmarks.funded_finalist_retry \
  --execute DESIGN_SHA256 --out NEW_REPORT.json
```

Two replays from a clean source export matched byte for byte with sockets and DNS blocked. The runner reproduced 132 published control-panel records, rejected a stale seal, and refused an existing report path. Three focused tests checked reserve admission, distinct lookups, and exact validation and critical protection across 512 seeded cap checks. Storage Guard measured 12.0 GiB free. The 22.1 MB scratch overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_funded_finalist_retry.py) · [Verification receipt](funded-finalist-retry-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
