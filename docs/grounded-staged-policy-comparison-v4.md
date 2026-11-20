# Test opening dominance against split-safe GEPA

Version 4 enables the [opening dominance proof](opening-dominance.md) in the opening-only CPO arm. The staged CPO arm, three GEPA controls, corpus, opening proposals, admission cases, and independent panel are the same as in [version 3](grounded-staged-policy-comparison-v3.md). The development seal binds the new proof and entry point.

| Fixture | Opening-only search uses, v3 → v4 | v4 development / confirmation physical requests |
| --- | ---: | ---: |
| Every opening rewrite needs repair | 117 → 110 | 626 / 144 |
| Ticket rewrite is already correct | 111 → 106 | 550 / 128 |

Every selected prompt, admission decision, and paired score matched v3. Staged CPO qualified on both scripted profiles in development and confirmation. The lower number of attributed opening-only reads did not reduce physical fixture calls because the other arms had already paid for those replies. Both stages reproduced through replay. [Plan and fixture receipts](grounded-staged-policy-comparison-v4-results.json)

## Reproduce offline

Use GEPA 0.1.4 and fresh paths. The second command prints the bound independent panel seal for `PANEL_SHA256`. Pass `--profile perfect-ticket-rewrite` in both fixture phases to run the second profile.

```sh
python -B -m benchmarks.grounded_staged_opening_dominance_comparison \
  --fixture f354c8f6be4bf658e7ca93bc170beaaade3841f22ee70fd6bf8423cf6a596279 --out DEV
python -B -m benchmarks.grounded_staged_opening_dominance_comparison --development DEV
python -B -m benchmarks.grounded_staged_opening_dominance_comparison \
  --development DEV --fixture PANEL_SHA256 --out PANEL
python -B -m benchmarks.grounded_staged_opening_dominance_comparison \
  --development DEV --replay PANEL --out PANEL_REPLAY
```

Development reserves up to 1,920 physical requests and confirmation up to 288. The portable study applies the efficiency gate to attributed search uses. The Luna provider protocol also applies the gate to actual reply token usage at the sealed rates. Fresh model quality and costs remain unverified.
