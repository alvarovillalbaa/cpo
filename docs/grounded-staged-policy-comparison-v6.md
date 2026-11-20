# Compare paired rewrite orders on the same paid samples

Version 6 adds observed-charge ordering alongside the row-paired field selector. Both can acquire only replies already used by fixed-rewrite GEPA. The charge-aware selector sees a reply's integer charge after acquiring it. The native fixed-rewrite, row-paired, and charge-aware arms must produce the same nomination and admission decision and share each matched holdout and confirmation reply.

The staged policy, opening dominance, and all three GEPA controls use the same datasets, model-independent gates, and supplied-opening logic as version 5. The extra arm has its own logical evaluation and admission limits. It adds zero physical requests to the 1,920-request development and 288-request independent confirmation ceilings. Provider-adapted use derives observed charges from the same reconciled token receipts that are used for the efficiency gate.

## Reproduce a fixture

Use GEPA 0.1.4 and fresh output paths. The portable fixture uses gain per read when it has no price. The focused tests also exercise explicit per-reply prices.

```sh
python -B -m benchmarks.grounded_staged_charge_comparison
python -B -m benchmarks.grounded_staged_charge_comparison \
  --fixture 2942ecd724f21d16a765b02e43945cbea2514061e360f3b4eb3536200b5da099 \
  --out DEV
python -B -m benchmarks.grounded_staged_charge_comparison --replay DEV --out DEV_REPLAY
python -B -m benchmarks.grounded_staged_charge_comparison --development DEV
python -m pytest -q tests/unit/test_grounded_staged_charge_comparison.py
```

The [version 5 protocol](grounded-staged-policy-comparison-v5.md) keeps its original source revision and seal. The prospective version 6 protocol requires its own run and independent confirmation.
