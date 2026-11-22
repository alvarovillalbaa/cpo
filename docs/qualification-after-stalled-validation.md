# Qualify one challenger after strict validation stalls

The two-sided cycle usually keeps the incumbent on MMLU. The new replay preserves its qualification precheck and complete strict validation search. If that search opens and returns no nominee, it can use the unspent part of the same 19-lookup search cap to find one fallback. Critical validation cases retain the original search. Any fallback still has to pass the original independent qualification against the incumbent. [Headroom from the original search](two-sided-finalist-challenge.md) · [Benchmark runner](../benchmarks/qualification_after_stalled_validation.py)

- **Witnessed validation nonloss** considers candidates with a paid pass on an already observed incumbent miss. It tries the most advanced proofs first and admits a challenger only when the observed grades prove that its validation total cannot fall below the incumbent's.
- **Disjoint training gain** prioritizes challengers by their paid paired validation margin, smoothed pass rate, and number of observations. It can nominate a challenger that ties or loses on validation if the first two scheduled training cases prove a strict gain. Training replies share the search cap and stay outside the qualification panel.

The earlier and disjoint MMLU cohorts and the original BBH cohort contain 86 archived model panels and 2,752 seeded trials per margin. Both native GEPA modes keep the same candidates and case splits. Their subject-tuned menu includes all six previously measured qualification wrappers at every search cap from 6 through 180. The menu is repriced at each fallback's realized lookup budget. [Published native menu](paired-order-gepa-comparison.md)

## Results

Each entry gives the fallback's change in held-out passes and paid lookups versus strict two-sided CPO. The GEPA gap is measured at the fallback's own realized budget. [BBH results](qualification-after-stalled-validation-bbh-results-v1.json) · [Earlier MMLU results](qualification-after-stalled-validation-earlier-mmlu-results-v1.json) · [Disjoint MMLU results](qualification-after-stalled-validation-disjoint-mmlu-results-v1.json)

| Cohort and gain | Witnessed nonloss change | Gap to GEPA | Training gain change | Gap to GEPA |
| --- | ---: | ---: | ---: | ---: |
| BBH, one | +30 / +538 | −45 | +49 / +1,880 | −81 |
| BBH, two | +17 / +339 | −557 | −2 / +1,560 | −630 |
| Earlier MMLU, one | −3 / +330 | −38 | −1 / +1,367 | −36 |
| Earlier MMLU, two | +1 / +145 | −22 | 0 / +781 | −23 |
| Disjoint MMLU, one | −23 / +284 | −45 | −6 / +1,397 | −28 |
| Disjoint MMLU, two | −4 / +136 | −22 | 0 / +690 | −19 |

At one gain, 262 MMLU trials with a validation stall contained a candidate that met the original independent qualification and improved the incumbent's held-out score. Only 34 had an option with strict validation gain, 26 had an option with a validation tie and a paired repair, and 25 had an option with a strict gain on the two training cases. These counts can overlap. The hindsight check prices no proof and reads complete archived grades only after selection. It shows that these extra search requirements cover a small part of the available MMLU improvement.

Both fallbacks added lookups in every cohort and margin. The extra BBH passes stayed below the subject-tuned GEPA menu at matched spend. The witnessed nonloss and training policies remain benchmark-only. Fresh-model superiority remains unverified.

## Reproduce offline

Use the pinned GEPA 0.1.4 benchmark dependency and a fresh output path. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_after_stalled_validation \
  --cohort BBH --execute cdb2eb428c34a8749e07522be8e441dc8a77be97f4d1d2e915471b04757ce0b5 \
  --out NEW_BBH_REPORT.json

PYTHONHASHSEED=0 python -B -m benchmarks.qualification_after_stalled_validation \
  --cohort earlier-screen-cohort \
  --execute 2883c62bff2aa6f51d2e8b2dc518c5b0033cb9d0918fae95e5bfa97dc279f7e7 \
  --out NEW_EARLIER_MMLU_REPORT.json

PYTHONHASHSEED=0 python -B -m benchmarks.qualification_after_stalled_validation \
  --cohort disjoint-transfer-cohort \
  --execute bb100657ae1a724d38a443547d63b57ad7f5347f7e2150cf8d65c0d3d123de9e \
  --out NEW_DISJOINT_MMLU_REPORT.json
```

Two offline runs of each phase matched byte for byte. The BBH report hash is `ce56c5641817a8b2203e9694000b9b77f395881c7081040d45d214b1bdbd3976`. Earlier MMLU is `19cbe0dd8151378945511ef2825aee154853b4f5f06f43fee633fd38e14e1aa9` and disjoint MMLU is `7616f55fee0968ac29bf34c4b7b4314592183e603a86a9ccda8bbe06d06ce719`. The replay reproduced all 172 baseline panel-by-margin traces and repriced all 2,100 native settings per cohort. Thirteen targeted tests passed. Storage Guard measured 1.9 GiB free. The scratch overlay and publication checkout fit the standing 0.2 GiB LAB exception. DNS and outbound sockets were blocked, and no provider requests were sent. [Focused tests](../tests/unit/test_qualification_after_stalled_validation.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
