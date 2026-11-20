# Stop opening validation once the promotion decision is known

Pass `certify_validation=True` to `run_opening_screen_cycle` when using a finite qualification limit below the cost of the full paired panel. The opening screen selects the same challenger. The new check reuses its search replies and stops validation when no possible completion can change the promotion decision. A promotion requires a strict net gain, no family with a net loss, and no critical case on which the incumbent passes and the challenger fails. The existing paired qualification still runs after validation. Expected qualification under a full panel retains its exact validation counts.

For each family, the lower bound treats every missing incumbent reply as a pass and every missing challenger reply as a failure. The upper bound reverses those assumptions. An observed critical loss, a negative upper bound in any family, or an upper bound below one total gain rejects the challenger. Promotion requires a positive lower bound across all rows, nonnegative lower bounds in every family, and enough evidence to rule out all critical losses. The checker resolves uncertain critical pairs first and reads the incumbent first within each pair. Ordering affects which replies are needed. The bounds determine the decision.

## Archived Sol replay

The experiment reran the same 240 paths over 36 distinct scoring cases used in the fixed-opening GEPA comparison. It held the prompts, data splits, proposal slots, admission policy, and token pricing constant. The certificate preserved every CPO nominee, admission outcome, and held-out result. It saved 119 search reads across 93 paths. Every other path used the same number of reads. [Exact results](certified-opening-validation-results-v1.json) · [GEPA control design](grounded-gepa-cache-controls.md)

| Policy | Held-out passes | Matched critical losses vs. GEPA | Search reads | Estimated cost at archived rates |
| --- | ---: | ---: | ---: | ---: |
| Opening-only CPO | 382/480 | 0 | 1,517 | $21.673896 |
| CPO with certified opening validation | 382/480 | 0 | 1,398 | $20.842344 |
| Fixed-opening GEPA, two-case minibatch | 382/480 | 0 | 1,920 | $23.456712 |

CPO cost **11.15% less** than the fixed-opening GEPA control across all paths. The two archived seed sets showed 11.27% and 11.02% savings, respectively. Outage on its own showed 7.17% savings. Both offline runs reproduced the same result. Fresh model quality, savings, and independent qualification remain unverified.

## Run the decision tests

```sh
python -m pytest -q tests/unit/test_opening_validation.py
```

The exhaustive test compares 4,096 fixed outcome matrices, critical masks, and budgets against full validation through the normal opening-cycle entry point. It checks the selected prompt, the complete qualification decision, and the set of paid validation reads. The focused regression checks that an observed critical loss prevents reads of the remaining unneeded case. [Certificate implementation](../cpo/opening_validation.py) · [Tests](../tests/unit/test_opening_validation.py)
