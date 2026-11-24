# Transfer the frozen ARC-AGI halving setting to language archives

Both rotated ARC-AGI calibration folds chose four challengers and a 19-read validation cap. This test transfers that setting unchanged to 64 archived BBH, LMentry and MMLU model-and-task panels. Both the math calibration and qualification-order fit exclude these target tasks. Each episode carries the deployed prompt forward through three cycles, with eight available challengers per cycle, fresh role-disjoint search and qualification cases, and a fixed final holdout. [Math setting](recorded-math-reinvested-halving.md) · [Language layouts](continuous-archive-routing.md) · [Transfer runner](../benchmarks/reinvested_halving_language_transfer.py)

The transfer uses the math study's frozen joint qualification order. The public cycle's default proof order reproduced every validation callback, nomination and deployment. The two proof orders can differ in lookup cost. For the primary setting and both diagnostics, certified halving with reuse disabled matches the eager halving nominee and qualification on every cycle. Its validation reads are a subset of eager halving's reads. This isolates spending saved slots from the read-skipping rule itself.

The comparison charges actual validation and qualification reads across the three cycles. It directly replays the strongest affordable common uniform and halving settings, the strongest affordable task-specific simple schedule, and the affordable native GEPA anchors from the earlier full-grid sweep. The GEPA anchors bound the optimum where archived budgets bracket the transfer cost. A directly replayed anchor gives a feasible score when the upper bound is unavailable. The paired intervals resample held-out case IDs within each task, keeping models, seeds and selected control settings aligned.

## Fixed four-challenger transfer

Cells give final held-out passes and total paid lookups. The GEPA column gives a directly attained schedule under the transfer cost.

| Cohort | Transferred CPO | Same-setting eager halving | Existing CPO router | Task-tuned simple | Task-tuned GEPA anchor |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 19,804 | 6,347 / 21,205 | 6,389 / 13,797 | 6,433 / 19,785 | 6,367 / 18,699 |
| Bounded LMentry | 5,951 / 20,166 | 5,951 / 21,051 | 6,321 / 15,711 | 6,547 / 20,026 | 6,135 / 19,138 |
| Bounded MMLU | 7,715 / 11,477 | 7,715 / 12,663 | 7,725 / 7,696 | 7,739 / 11,010 | 7,718 / 8,488 |
| Four-case MMLU | 22,357 / 16,433 | 22,357 / 17,858 | 22,381 / 12,145 | 22,413 / 15,793 | 22,369 / 9,289 |
| Tie BBH | 2,146 / 14,123 | 2,146 / 14,604 | 2,204 / 13,130 | 2,183 / 13,963 | 2,126 / 12,939 |
| Tie LMentry | 978 / 7,033 | 978 / 7,132 | 1,028 / 7,195 | 1,013 / 6,884 | 919 / 6,508 |
| Additional MMLU | 7,391 / 10,897 | 7,391 / 11,958 | 7,384 / 7,257 | 7,411 / 10,021 | 7,399 / 6,001 |

Six validation rows with four challengers cost at most 16 eager lookups. A cap of 19 leaves enough room for every round, so reinvestment never buys an extra row. Read skipping saves 6,538 lookups over the matched eager setting with the same final scores. The strongest affordable simple schedule scores higher and costs less in all seven cohorts. The frozen setting also loses to an affordable task-tuned GEPA anchor in five cohorts. It scores above the published task-tuned GEPA upper bounds on tie BBH and tie LMentry, where the simple controls still score higher and cost less.

## When the search cap can bind

Two diagnostic settings keep the validation roles unchanged. Four challengers at cap 15 have one lookup fewer than the eager full-panel quote. Eight challengers at cap 19 widen the roster while keeping the math setting's cap. Both settings compare reuse against the same certified screen without reuse. They also reprice the complete simple-control menu at actual spend.

| Cohort | Four / 15 extra rounds | Held-out change from reuse | Eight / 19 extra rounds | Held-out change from reuse |
| --- | ---: | ---: | ---: | ---: |
| Bounded BBH | 781 | −6 | 1,594 | −5 |
| Bounded LMentry | 552 | +25 | 947 | +51 |
| Bounded MMLU | 555 | 0 | 1,364 | −5 |
| Four-case MMLU | 699 | +3 | 1,651 | −1 |
| Tie BBH | 334 | −4 | 515 | −2 |
| Tie LMentry | 88 | +5 | 73 | +7 |
| Additional MMLU | 496 | +1 | 1,204 | +1 |

Reinvestment funded 3,505 additional rounds with four challengers and 7,348 with eight. Bounded LMentry had positive paired ranges against the same screen without reuse at both settings, +2 to +47 and +10 to +90. The other paired ranges included zero. The task-tuned simple schedule remained ahead at both diagnostic budgets in every cohort. This isolates a benefit from reinvestment on bounded LMentry and leaves the broader screening policy behind the strongest simple alternative. The estimates cover archived candidate selection over three cycles. They do not measure fresh proposals or live model performance.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview the seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.reinvested_halving_language_transfer \
  --cohort bounded-LMentry \
  --execute 3366c22f37bfdc3e88eb2038611498d0d370320feffee7db083327d73e3d83d4 \
  --out NEW_REPORT.json
```

[Bounded BBH](reinvested-halving-language-transfer-bounded-bbh-v1.json) · [Bounded LMentry](reinvested-halving-language-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](reinvested-halving-language-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](reinvested-halving-language-transfer-four-case-mmlu-v1.json) · [Tie BBH](reinvested-halving-language-transfer-tie-bbh-v1.json) · [Tie LMentry](reinvested-halving-language-transfer-tie-lmentry-v1.json) · [Additional MMLU](reinvested-halving-language-transfer-additional-mmlu-v1.json)

Sixteen targeted tests passed. Two replays per cohort matched byte for byte with DNS and outbound sockets blocked. Each setting covered 2,048 episodes and 6,144 cycle layouts. The study issued zero provider requests. Storage Guard measured 10.0 GiB free. The temporary source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_reinvested_halving_language_transfer.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
