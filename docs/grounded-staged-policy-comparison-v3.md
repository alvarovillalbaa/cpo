# Test certified opening validation against split-safe GEPA

Version 3 enables [certified opening validation](certified-opening-validation.md) for the opening-only CPO arm. The staged CPO arm and three GEPA controls retain the algorithms from the [split-safe comparison](grounded-staged-policy-comparison-v2.md). The corpus, supplied opening, independent admission, qualification panels, and pass gates are unchanged. The prospective seal binds the certificate source. An independent panel can bind only to replay-verified development that qualifies under the current protocol.

| Fixture | Opening-only search uses, v2 → v3 | v3 development / confirmation physical requests |
| --- | ---: | ---: |
| Every opening rewrite needs repair | 131 → 117 | 626 / 144 |
| Ticket rewrite is already correct | 119 → 111 | 550 / 128 |

Both fixtures preserved selected prompts, admission decisions, and matched scores. Staged CPO qualified in both stages. Removing opening-only lookups reduced the arm's attributed search uses. Other arms had already paid for the skipped replies, so the total number of physical requests stayed the same. The 1,920-request development and 288-request confirmation ceilings remain in force. [Sealed plan and replay results](grounded-staged-policy-comparison-v3-results.json)

## Reproduce offline

Use GEPA 0.1.4 and fresh output directories. The second command prints the independent panel seal for `PANEL_SHA256`. Pass `--profile perfect-ticket-rewrite` in both fixture phases to run the second fixture.

```sh
python -B -m benchmarks.grounded_staged_certified_opening_comparison \
  --fixture 638d92527ec4b4aaa25cbe623cdbbf5021edb1df8b7980e93a89f164916d951c --out DEV
python -B -m benchmarks.grounded_staged_certified_opening_comparison --development DEV
python -B -m benchmarks.grounded_staged_certified_opening_comparison \
  --development DEV --fixture PANEL_SHA256 --out PANEL
python -B -m benchmarks.grounded_staged_certified_opening_comparison \
  --development DEV --replay PANEL --out PANEL_REPLAY
```

The fixture outcomes establish replay and attribution behavior. Live quality and token savings remain unverified. Use the original published revision for a v2 replay.
