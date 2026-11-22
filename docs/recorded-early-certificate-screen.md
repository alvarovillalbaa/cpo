# Compare two budgets for early challenger screening

The remaining-budget experiment found plausible gains at cap 13 that the original race reached too late. This replay uses the first case the incumbent missed as a shared probe for an affordable prefix of the challenger roster. Both policies consider probe passes first, break ties in roster order, credit the probe toward an exact strict-gain certificate, and qualify the first certified nominee independently. [Remaining-budget result](recorded-remaining-validation-budget.md) · [Replay runner](../benchmarks/recorded_early_certificate_screen.py)

The complete-panel reserve keeps enough lookups to finish all unread validation cases for one finalist. The minimum-proof reserve keeps only the number of favorable reads needed to certify a strict gain, assuming the probe passes. It reaches more challengers at a low cap and can run out of budget after a failed reply. Actual promotion still requires a paid strict gain, preservation of the incumbent’s critical passes, and independent qualification.

The primary policy uses the minimum-proof reserve at cap 13. The gate requires a positive point margin and a nonnegative lower paired bound against the best affordable fixed CPO or native GEPA setting, including retained starts. Both methods use the same 896 previously scored MMLU trials. Each paired draw reselects the control using realized search-plus-qualification cost.

| Policy | Probe lookups | Validation nominees / qualified promotions | Held-out passes / paid lookups | Margin and paired 95% range |
| --- | ---: | ---: | ---: | ---: |
| Complete-panel reserve, cap 13 | 1,340 | 160 / 36 | 26,613 / 10,253 | −12, −40 to +5 |
| Minimum-proof reserve, cap 13 | 2,537 | 26 / 4 | 26,621 / 9,343 | −4, −10 to +1 |
| Either reserve, cap 32 | 5,360 | 332 / 70 | 26,645 / 18,989 | −17, −33 to −2 |

At cap 13, the minimum-proof reserve gained 11 passes and saved 253 lookups versus the original exact race. It missed the gate against retaining the starts, which scored 26,625 at zero cost. The wider probe spent 1,197 more lookups on screening than the complete-panel reserve and used 1,449 fewer on certificates. Only four candidates made it through independent qualification. At cap 32, both reserves could screen the entire roster and produced identical decisions. The exact race at cap 29 led by 17 passes and spent 168 fewer lookups. Fresh-model performance remains unverified. [Full results and matched comparisons](recorded-early-certificate-screen-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_early_certificate_screen
python -B -m benchmarks.recorded_early_certificate_screen \
  --execute cc55f0838666bd296070797947dbe890aff539c33a5ec93b9e2c63864c8f94de \
  --out NEW_REPORT.json
```

The initial archive replay exposed an optional training adapter that requires a fully scored validation panel. The final seal uses the existing validation-only adapter and retains the incumbent precheck and independent qualification. The CLI rejected the initial seal. Two clean-export replays with DNS and sockets blocked matched byte for byte at SHA-256 `f45d89bace132d6b51bdb2e340e484af544ee22ed40b2e4d7ea110b6d1d3a2e8`. Thirty-four targeted tests passed. A direct audit checked paid certificates, independent qualification, and scoring across 3,584 paths. Storage Guard measured 3.1 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Regression tests](../tests/unit/test_recorded_early_certificate_screen.py)
