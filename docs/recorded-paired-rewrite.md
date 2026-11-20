# Prove the paired gains for a fixed rewrite

CPO can use GEPA's supplied two-case minibatch and strict validation gain rule while skipping paid reads that cannot change either decision. Across 760 archived ARC-AGI and AIME paths, `select_paired_rewrite` matched native fixed-rewrite GEPA on every nominee, independent admission decision, and held-out score. On each path, CPO read a subset of the same prompt-and-case replies. [Replay results](recorded-paired-rewrite-results-v1.json) · [Implementation](../cpo/paired_rewrite.py)

| Archive and incumbent | Matched passes | Native → paired paid reads | Read reduction | ARC cost at recorded rates |
| --- | ---: | ---: | ---: | ---: |
| ARC original | 1,244 / 1,920 | 810 → 615 | 24.07% | $75.11 → $58.83 |
| ARC rotated | 13,373 / 17,280 | 4,355 → 2,105 | 51.66% | $555.36 → $271.86 |
| AIME original | 497 / 1,000 | 414 → 256 | 38.16% | Unavailable |
| AIME rotated | 4,073 / 8,000 | 3,206 → 1,904 | 40.61% | Unavailable |

The proof first checks whether the incumbent already passes every minibatch case. A strict gain is impossible in that case. Otherwise, it computes lower and upper bounds on paired gain, stopping as soon as the outcome is determined. A minibatch gain unlocks the full validation gate, which reuses the same paid replies. Independent admission still runs separately. The public selector compares binary totals for one supplied rewrite. The higher-scoring ARC CPO policy with two supplied proposals remains a separate option with a different cost and accuracy profile. [Two-proposal comparison](recorded-opening-dominance-transfer.md)

The harness recovers the seeded first minibatch by tracing native GEPA 0.1.4 with synthetic replies. Neither selector uses scores from the held-out split to choose a prompt. Native control trace hashes matched the published transfer benchmark. Search and admission count toward cost. Recorded ARC evaluator charges supply the dollar estimates, and the shared supplied rewrite carries no charge in either arm.

## Reproduce offline

Use the published source and GEPA 0.1.4. The first command prints the seal and the second writes a fresh report.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_paired_rewrite
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_paired_rewrite \
  --execute 426c96edce347f5fc25fdbaae683aae32b1cec88e56262c6709a3d05135e5975 \
  --out NEW_REPORT.json
python -m pytest -q tests/unit/test_paired_rewrite.py
```

The focused test verifies selection and read-set inclusion on all 256 binary outcome matrices for four cases. Two offline replays matched byte for byte with socket and DNS access blocked. Fresh proposal generation and model performance remain unverified.

The same two-gate approach also works with uniform field credit and preserves native rounding on ties. [Typed Sol comparison](recorded-paired-field-rewrite.md)
