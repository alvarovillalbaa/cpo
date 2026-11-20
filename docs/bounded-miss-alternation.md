# Alternate first probes with bounded incumbent lookahead

In the affordable-path audit, 50 of 85 losing comparisons stopped before a viable challenger showed a paid gain on an incumbent miss. In 49 of those 50 comparisons, each matching challenger at that stage had one validation lookup. Earlier miss rotation gained accuracy on some panels and increased lookup costs. This replay targets the deferred first-gain branch and limits how much it spends finding another case. [Affordable challenger audit](affordable-challenger-attribution.md) · [Earlier miss rotation](prompteval-coverage-rotation.md)

The first challenger uses the original witness. If that probe fails, the selector inspects at most the next two incumbent cases to find a second miss. It then alternates the remaining challengers between those misses. If no second miss appears, all challengers use the original witness. Each challenger gets one first probe. The first challenger to pass its assigned probe still needs the existing strict validation certificate and independent qualification. The search keeps the full proof reserve and reuses any lookahead replies needed by that proof.

The matched scan arm buys the same bounded lookahead and keeps the shared original witness. It must preserve every original deployment. The other routing branches, proposal order, archive checks, cap, and holdout stay fixed. The comparison uses 28 archived Llama, Mistral, Gemma, and Flan panels, with both original cap-52 GEPA modes, batched GEPA at cap 47, and retaining the start. [Runner](../benchmarks/bounded_miss_alternation.py)

## Results

Each cell gives final holdout passes and total paid search and qualification lookups.

| Method | Llama and Mistral | Gemma and Flan |
| --- | ---: | ---: |
| Original CPO route | 17,724 / 49,330 | 17,435 / 35,496 |
| Shared probe with matched scan | 17,724 / 50,422 | 17,435 / 36,577 |
| Bounded alternation | 17,732 / 52,150 | 17,459 / 37,785 |
| Batched GEPA, cap 47 | 17,687 / 45,679 | 17,407 / 31,608 |
| Batched GEPA, cap 52 | 17,694 / 57,271 | 17,422 / 40,184 |
| Sequential GEPA, cap 52 | 17,721 / 81,537 | 17,409 / 60,951 |

The matched scan preserved all original deployments and increased paid cost by 2,173 lookups in total. Bounded alternation changed 77 final selections, gained 32 net holdout passes over the original route, and used 5,109 more lookups. It applied 5,418 alternate first probes and produced 275 finalists from them. Across the 85 audited affordable-path losses it recovered four comparisons, including two of the 50 that had stopped without a paid gain witness. The original GEPA controls were unchanged. [Per-panel totals and recoveries](bounded-miss-alternation-results-v1.json)

Compared with cap-52 batched GEPA, bounded alternation saved 8.9% on Llama and Mistral and 6.0% on Gemma and Flan. The joint accuracy ranges against both cap-52 GEPA modes were −46 to +66 and −12 to +84 respectively. Neither cohort cleared the 10% savings gate. CPO retains its original deferred screen. The study uses fixed recorded prompts and provides no fresh-model result.

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two source-export replays matched byte for byte with sockets and DNS blocked and reproduced 140 published panel-control records. Three focused tests checked the two-read bound, exact certification, and critical-pass preservation. The CLI rejected an incorrect seal and preserved an existing report. Storage Guard measured 12.6 GiB free. The 20.9 MB temporary overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_bounded_miss_alternation.py) · [Verification receipt](bounded-miss-alternation-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.bounded_miss_alternation \
  --execute 4d96ef9d1169dc47ee9b16bd6056beb81c3c56f687c1fbb72eb980c85c8adf84 \
  --out NEW_REPORT.json
```
