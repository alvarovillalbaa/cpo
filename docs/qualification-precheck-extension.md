# Extend an impossible qualification precheck with two reserved cases

The two-sided CPO cycle often retained the MMLU incumbent before selecting a challenger. This benchmark reserves two extra cases for each seeded trial. The cases come from the same recorded subject outside the original training, validation, qualification, and final holdout splits. Both CPO and GEPA activate the same reserve when the required gain becomes impossible on the original four-case panel. They retain the paid incumbent prefix and require the same exact net gain on all six cases. The original four-case paths stay active whenever the requested gain remains possible. [Earlier MMLU headroom audit](two-sided-finalist-challenge.md) · [Replay driver](../benchmarks/qualification_precheck_extension.py)

The earlier and disjoint MMLU cohorts contribute 58 archived model panels and 1,856 seeded trials per qualification margin. CPO keeps the two-sided validation cycle and its 19-lookup search cap. Sequential and same-parent batched GEPA use every integer search cap from 6 to 180. The matched GEPA ceiling gives each subject a mode and cap under the same extension and margin, and constrains total lookups to CPO's measured spend. The expanded ceiling also permits all six previously measured qualification wrappers. The subject choices use held-out scores and are reported as hindsight bounds on the tested native settings. [Earlier native comparison](paired-order-gepa-comparison.md)

## Results

Each entry gives held-out passes and paid lookups. The two GEPA columns use the extended CPO budget. [Earlier MMLU results](qualification-precheck-extension-earlier-mmlu-results-v1.json) · [Disjoint MMLU results](qualification-precheck-extension-disjoint-mmlu-results-v1.json)

| Cohort and gain | Two-sided CPO | CPO with extension | GEPA with the same extension and gain | Expanded GEPA menu |
| --- | ---: | ---: | ---: | ---: |
| Earlier MMLU, one | 26,619 / 13,363 | 26,617 / 14,763 | 26,653 / 11,648 | 26,654 / 10,802 |
| Earlier MMLU, two | 26,630 / 9,571 | 26,632 / 13,052 | 26,631 / 5,952 | 26,654 / 10,802 |
| Disjoint MMLU, one | 56,094 / 12,701 | 56,096 / 14,575 | 56,116 / 13,658 | 56,117 / 12,794 |
| Disjoint MMLU, two | 56,094 / 8,893 | 56,094 / 12,461 | 56,074 / 4,512 | 56,116 / 11,534 |

At one gain, 433 otherwise blocked prechecks activated the reserve. They yielded 50 CPO nominations and five deployments, with zero net held-out improvement and 3,274 additional lookups. At two gains, 1,038 prechecks activated the reserve. They yielded 79 new nominations and one deployment, adding two held-out passes and 7,049 lookups. The two-gain candidate beat the same-gate GEPA score on both cohorts and paid more than twice the attaining schedule on each. An affordable setting from the expanded GEPA menu led in all four comparisons. The extension remains benchmark-only.

## Reproduce offline

Use Python 3.12 and the pinned GEPA 0.1.4 benchmark dependency. Run each cohort with its matching seal and a fresh output path. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_precheck_extension \
  --cohort earlier-screen-cohort \
  --execute 3c3a1fad15d624551a2d4a36f45db77f88e8d15f5ad4eb4a0696a0dd68ba2c3c \
  --out NEW_EARLIER_REPORT.json

PYTHONHASHSEED=0 python -B -m benchmarks.qualification_precheck_extension \
  --cohort disjoint-transfer-cohort \
  --execute c3c4a85bb7c71c81bba3c844a4a0ffad8db46d0be6f89b7ee75115c54438729b \
  --out NEW_DISJOINT_REPORT.json
```

Two offline executions of each cohort matched byte for byte. The earlier report hash is `f644f3dfa9d7f475d71e1d8a5f23f3b75d716e78e932e51a8375f434a96a6f0a` and the disjoint report hash is `456573282281872365fccdaf9b5bff3c18e5ab7d75aca5572cd3bd726f910cb0`. Each cohort checked 2,100 original and 700 extended GEPA settings. The replay recomputed the prior native subject ceilings, reproduced all 116 two-sided panel-by-margin traces across the two cohorts, and checked inactive-path parity for CPO and matched GEPA. Twelve targeted tests passed. Storage Guard measured 2.0 GiB free. The source export and publication checkout fit the standing 0.2 GiB LAB exception. DNS and outbound sockets were blocked, and no provider requests were sent. [Focused tests](../tests/unit/test_qualification_precheck_extension.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
