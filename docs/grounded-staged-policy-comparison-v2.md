# Compare CPO against split-safe GEPA controls

Version 2 gives sequential and batched GEPA stable case IDs for separate training and validation splits. It also adds a fixed-opening GEPA control that receives the common rewrite, reuses validation replies for its two-case minibatch, and generates no later proposals. Staged and opening-only CPO both face all three GEPA controls. Cohorts, prompt generation, admission, and qualification retain their original definitions. Either CPO policy can bind independent confirmation if it qualifies in development. [Cache correction and archived comparison](grounded-gepa-cache-controls.md) · [Runner](../benchmarks/grounded_staged_policy_comparison.py)

| Fixture profile | Development physical requests | Confirmation physical requests | Staged CPO passes in development / confirmation | Strongest GEPA passes in development / confirmation |
| --- | ---: | ---: | ---: | ---: |
| Every opening rewrite needs repair | 626 | 144 | 108 / 48 | 100 / 44 |
| Ticket rewrite is already correct | 550 | 128 | 108 / 48 | 100 / 44 |

Staged CPO qualified in both phases. Opening-only scored 80 and 34 passes on the all-faulted fixture and 84 and 36 on the perfect-ticket fixture. The new fixed-opening GEPA control matched those opening-only pass totals. All four archives replayed byte for byte. Fourteen focused tests passed, including the split cache regression, per-arm sample attribution, and independent confirmation binding when opening-only qualifies by itself. [Plan and fixture manifests](grounded-staged-policy-comparison-v2-results.json)

## Reproduce offline

Use GEPA 0.1.4 and fresh output paths. The development ceiling is 1,920 physical requests. Independent confirmation is separately bound to the qualifying development archive and has a 288-request ceiling. The second command prints the panel seal used as `PANEL_SHA256`. Add `--profile perfect-ticket-rewrite` in both fixture phases to run the second profile.

```sh
python -B -m benchmarks.grounded_staged_policy_comparison \
  --fixture 68acd0639b31533726a4163f35e5ea9539860e2f718072f16c2bcfb9bbc388db --out DEV
python -B -m benchmarks.grounded_staged_policy_comparison --development DEV
python -B -m benchmarks.grounded_staged_policy_comparison \
  --development DEV --fixture PANEL_SHA256 --out PANEL
python -B -m benchmarks.grounded_staged_policy_comparison \
  --development DEV --replay PANEL --out PANEL_REPLAY
```

The earlier seal and fixture archives belong to the [original policy comparison](grounded-staged-policy-comparison.md). These fixtures verify the corrected protocols on scripted replies. Fresh model performance and spending remain open.
