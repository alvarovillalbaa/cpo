# Prove the paired gains for a fixed rewrite

CPO can use GEPA's supplied two-case minibatch and strict validation gain rule while skipping paid reads that cannot change either decision. Across 760 archived ARC-AGI and AIME paths, `select_paired_rewrite` matched native fixed-rewrite GEPA on every nominee, independent admission decision, and held-out score. On each path, CPO read a subset of the same prompt-and-case replies. [Replay results](recorded-paired-rewrite-results-v1.json) · [Implementation](../cpo/paired_rewrite.py)

| Archive and incumbent | Matched passes | Native → paired paid reads | Read reduction | ARC cost at recorded rates |
| --- | ---: | ---: | ---: | ---: |
| ARC original | 1,244 / 1,920 | 810 → 615 | 24.07% | $75.11 → $58.83 |
| ARC rotated | 13,373 / 17,280 | 4,355 → 2,105 | 51.66% | $555.36 → $271.86 |
| AIME original | 497 / 1,000 | 414 → 256 | 38.16% | Unavailable |
| AIME rotated | 4,073 / 8,000 | 3,206 → 1,904 | 40.61% | Unavailable |

The proof first checks whether the incumbent already passes every minibatch case. A strict gain is impossible in that case. Otherwise, it computes lower and upper bounds on paired gain, stopping as soon as the outcome is determined. A minibatch gain unlocks the full validation gate, which reuses the same paid replies. Independent admission still runs separately. [Earlier ARC comparison with two supplied proposals](recorded-opening-dominance-transfer.md)

The harness recovers the seeded first minibatch by tracing native GEPA 0.1.4 with synthetic replies. Neither selector uses scores from the held-out split to choose a prompt. Native control trace hashes matched the published transfer benchmark. Search and admission count toward cost. Recorded ARC evaluator charges supply the dollar estimates, and the shared supplied rewrite carries no charge in either arm.

## Opt in to observed-charge ordering

`select_paired_rewrite` accepts an optional `observed_charge(prompt, row, observation)` callback. Return a nonnegative integer in a consistent unit, or `None` for an unavailable charge. The callback runs after an actual evaluation. The selector ranks the remaining full-validation reads by observed gain per charge and uses gain per read when either prompt lacks a usable charge. The minibatch and strict binary gates keep the same decisions. Row-paired ordering is the default.

```python
from cpo.paired_rewrite import select_paired_rewrite

nominee = select_paired_rewrite(
    incumbent, rewrite, validation_rows, minibatch_ids, evaluate,
    observed_charge=lambda _prompt, _row, reply: reply.feedback.get("charge_microusd"),
)
```

The package reproduced the exact archived request traces for the charge-aware replay. Across 760 ARC and AIME paths, it used 4,782 paid reads versus 4,880 for row-paired CPO and 8,785 for fixed-rewrite GEPA. All nominations, admission decisions, and 28,200 held-out scores matched. Pooled recorded ARC cost fell from $330.69 to $321.00 against row-paired CPO. It rose on 37 individual ARC paths. AIME used the missing-charge fallback.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_paired_rewrite --charge-aware
```

## Compare two rewrites from the same parent

`select_same_parent_rewrites` takes ordered `(rewrite, minibatch_ids)` pairs. Each proposal must beat the original incumbent on its own minibatch. Proposals that pass then compete on full validation, where ties retain the current leader. The gates share the same cache of paid replies. Independent admission still runs separately.

With identical supplied proposals and seeded minibatches, charge-aware CPO matched batched GEPA's nominee, admission decision, and held-out results on all 760 archived paths. Each CPO path read a subset of the corresponding GEPA path. Total reads fell from 11,697 to 8,468, a 27.6% reduction. The recorded ARC cost fell by 31.0%. Both arms count search and admission reads. The experiment supplied the same proposals to both arms, so proposal generation was outside the comparison. [Replay results](recorded-same-parent-paired-rewrite-results-v1.json)

| Archive and incumbent | Matched passes | Batched GEPA → CPO reads | ARC cost at recorded rates |
| --- | ---: | ---: | ---: |
| ARC original | 1,401 / 1,920 | 1,098 → 925 | $109.93 → $92.39 |
| ARC rotated | 13,507 / 17,280 | 5,722 → 3,767 | $725.14 → $483.52 |
| AIME original | 497 / 1,000 | 525 → 388 | Unavailable |
| AIME rotated | 4,073 / 8,000 | 4,352 → 3,388 | Unavailable |

Sequential GEPA scored 13,508 of 17,280 on rotated ARC, one pass above the batched result. The same-parent selector requires its proposals up front. Sequential proposal generation from updated parents remains a separate comparison. [Native control results](recorded-opening-dominance-transfer-results-v1.json)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_paired_rewrite --same-parent-charge-aware
```

## Reproduce offline

Use the [original row-paired source](https://github.com/alvarovillalbaa/cpo/tree/9addc6c7901b4d78c90a4c85d0920ec016da370e) and GEPA 0.1.4 to reproduce the sealed baseline. The first command prints the seal and the second writes a fresh report.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_paired_rewrite
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_paired_rewrite \
  --execute 426c96edce347f5fc25fdbaae683aae32b1cec88e56262c6709a3d05135e5975 \
  --out NEW_REPORT.json
python -m pytest -q tests/unit/test_paired_rewrite.py
```

The focused tests verify selection and read-set inclusion on all 256 binary outcome matrices for one proposal and all 4,096 matrices for two proposals over four cases. Two offline replays matched byte for byte with socket and DNS access blocked. Fresh proposal generation and model performance remain unverified.

The same two-gate approach also works with uniform field credit and preserves native rounding on ties. [Typed Sol comparison](recorded-paired-field-rewrite.md)
