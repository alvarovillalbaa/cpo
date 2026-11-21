# Test the public two-witness policy on disjoint MMLU tasks

The public selector reproduced the archived shortlists on LMentry and BBH. This replay freezes the selector and applies it to two published MMLU archives. It enrolls all panels other than formal logic and world religions, which appeared in earlier certificate experiments. The resulting 14 subjects and four model checkpoints were outside the earlier certificate and shortlist cohorts. The 28 model panels share 672 distinct held-out cases and run 32 seeded trials each. [Frozen selector](two-witness-pool.md) · [Code Llama and Merlinite archive](routed-finalist-model-transfer.md) · [Llama Instruct and Mistral archive](routed-start-model-confirmation.md)

The single-cycle replay keeps the eight-challenger rosters and disjoint training, validation, qualification, and holdout assignments. It compares the public selector, fixed halves, first certificate, and the earlier qualification-first CPO policy. It sweeps sequential and batched GEPA 0.1.4 at all integer search caps from 6 through 180. Lookup costs include search and qualification. Each draw resamples cases within subjects, retains both models and all seeds for each case, and selects the highest-scoring affordable fixed GEPA setting or the zero-cost start. [Replay runner](../benchmarks/recorded_two_witness_mmlu_transfer.py) · [Full results](recorded-two-witness-mmlu-transfer-results-v1.json)

| Policy | Held-out passes | Lookups | Margin and paired 95% range vs. best affordable setting |
| --- | ---: | ---: | ---: |
| Retain start | 26,625 | 0 | — |
| Public two-witness pool | 26,628 | 18,165 | +3, −19 to +15 |
| Fixed halves | 26,628 | 18,959 | +3, −20 to +15 |
| First certificate | 26,636 | 19,241 | +11, −13 to +25 |
| Qualification first | 26,635 | 23,505 | +10, −16 to +23 |

Retaining the start was the strongest affordable setting at each observed CPO budget. The cheapest GEPA setting that reached the two-witness score was batched at cap 51. It scored 26,630 with 25,664 lookups. The public selector's three-pass gain over the start remained inconclusive.

## Where the gain was limited

The selector deployed a challenger in 10 of 896 trials. An after-the-fact choice using the highest held-out score anywhere in each roster could reach 28,484 passes. Limiting that hindsight choice to challengers with strict gains on validation, the first half of training, and independent qualification lowered the ceiling to 26,669. Only 12 trials contained an eligible challenger with a better held-out score than CPO's deployment. Their combined upside was 41 passes, even with hindsight and no search cost. These diagnostic upper bounds use already recorded held-out replies after the replay.

A follow-up allowed exact training ties. It restored 33 deployments on this cohort and 12 on separate tasks and checkpoints. The paired quality range crossed zero on both cohorts. [Training threshold comparison](recorded-two-witness-training-nonloss.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and socket connections blocked, 73 targeted tests and five subtests passed. Two full replays matched byte for byte. Direct GEPA replay at cap 51 matched the reported score and cost over all 896 trials. The original selector parity receipt and live-plan preview reproduced. Storage Guard measured 4.7 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_two_witness_mmlu_transfer
python -B -m benchmarks.recorded_two_witness_mmlu_transfer \
  --execute e38cb34fe45dbc547a83183f79ffc2c17d1ae51e9dce1cfa421cdc76146f0482 \
  --out NEW_REPORT.json
```
