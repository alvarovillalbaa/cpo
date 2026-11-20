# Compare the paired field rewrite on the same paid replies

Version 5 adds [paired field rewrite selection](recorded-paired-field-rewrite.md) as a third CPO policy beside staged CPO and opening dominance. The corpus, existing policies, and three native GEPA controls retain the [v4 design](grounded-staged-policy-comparison-v4.md). The new arm uses the fixed-rewrite GEPA control's supplied rewrite and seeded minibatch.

The paired arm can read only a search or admission reply already used by fixed-rewrite GEPA. It must produce the same nomination and admission decision before scoring can begin. Each matched holdout scores the common selected prompt once and gives both arms that result. The benchmark still attributes each policy's search reads independently, so the paired proof can show a standalone saving. The trial's physical provider ceiling stays at 1,920 requests in development and 288 in confirmation.

| Fixture | Fixed-rewrite GEPA / paired CPO attributed search uses | Development / confirmation physical requests |
| --- | ---: | ---: |
| Every opening rewrite needs repair | 131 / 104 | 626 / 144 |
| Ticket rewrite is already correct | 128 / 100 | 550 / 128 |

Both v5 physical request journals matched their v4 fixture counterparts byte for byte. Existing selections, admission decisions, and scores reproduced. A separate tied-score fixture tested that the paired policy can bind independent confirmation. The Luna SDK additionally measures attributed token costs against the same gate. [Sealed plan and fixture receipts](grounded-staged-policy-comparison-v5-results.json)

## Reproduce offline

Use the published source and GEPA 0.1.4. The second command previews the bound panel seal for `PANEL_SHA256`. Use fresh output paths. Pass `--profile perfect-ticket-rewrite` in both phases to run the second fixture.

```sh
python -B -m benchmarks.grounded_staged_paired_rewrite_comparison \
  --fixture 44603fcce1a0acb4be7d10a7d23c30150c40e4da9b90eed6cdb858077152bb7a --out DEV
python -B -m benchmarks.grounded_staged_paired_rewrite_comparison --development DEV
python -B -m benchmarks.grounded_staged_paired_rewrite_comparison \
  --development DEV --fixture PANEL_SHA256 --out PANEL
python -B -m benchmarks.grounded_staged_paired_rewrite_comparison \
  --development DEV --replay PANEL --out PANEL_REPLAY
```

The fixture replays verify the cost accounting and qualification workflow. Fresh model performance remains unverified.
