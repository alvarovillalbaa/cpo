# Test the frozen settled episode runners on Promptolution

The packaged settled and feedback runners were frozen on the language archive. This replay applies both without refitting to Gemma 3 27B predictions for GSM8K and SST‑5. It uses the same pinned Promptolution records, starting prompts, three challenger pairs, and 90-case holdouts as the earlier witness study. The new comparison uses a separate six-case validation panel and four admission cases per cycle. The first two training cases are the CPO opening probes. The two-challenger rosters are smaller than those in the original settled fit. [Earlier Promptolution results](promptolution-witness-episode.md) · [Frozen CPO policies](feedback-episode-api.md)

Sequential and same-parent batched GEPA 0.1.4 receive the same candidate pairs, can use the original disjoint training windows, and carry qualified incumbents through all three cycles. The control menu includes 11 native GEPA settings, five successive-halving caps, both witness variants, and incumbent retention. Each comparison takes the highest-scoring control within the candidate's realized lookup budget. The paired bootstrap resamples physical holdout cases within each task, keeps their episodes together, and reselects the strongest affordable control on each draw. The direct feedback comparison reports its measured trade-off against settled CPO. [Benchmark](../benchmarks/promptolution_settled_episode_transfer.py)

## Archived transfer

Each task contains 32 episodes. Entries show held-out passes and paid lookups.

| Scope | Settled CPO | Feedback CPO | Best affordable native GEPA for either CPO runner | Feedback vs. settled paired 95% range |
| --- | ---: | ---: | ---: | ---: |
| GSM8K | 2,472 / 906 | 2,451 / 883 | 2,270 / 820 | −1.01 to −0.45 pp |
| SST‑5 | 1,452 / 1,549 | 1,434 / 1,465 | 1,295 / 1,256 | −1.04 to −0.21 pp |
| **Pooled** | **3,924 / 2,455** | **3,885 / 2,348** | **3,565 / 2,148** | **−0.92 to −0.42 pp** |

Both CPO runners exceeded the best affordable native GEPA setting and the strongest overall control on each task, with positive paired lower endpoints. Pooled, settled CPO gained 359 passes over affordable GEPA with a paired range of +4.34 to +8.07 percentage points. Feedback gained 320 passes with a range of +3.89 to +7.20. The strongest pooled overall control was successive halving at cap eight, with 3,820 passes on 2,011 lookups.

Feedback changed the schedule in 24 of 192 cycles. It saved 107 lookups and lost 39 passes relative to settled CPO. Both direct paired ranges favor settled CPO on score. The result supports keeping settled CPO as the accuracy baseline. The archive measures selection from existing programs and their recorded grades. It leaves fresh prompt generation and live superiority unverified. [Sealed report](promptolution-settled-episode-transfer-v1.json)

## Reproduce offline

Use the hash-pinned GEPA 0.1.4 environment and the reduced Promptolution corpus with SHA-256 `729bba5141874b28e3b172757d5e009f6e847f2b04050c75359d6273a01c9491`. The existing collector can rebuild the corpus from the pinned public CSVs. [Corpus collector](../benchmarks/promptolution_witness_capture.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.promptolution_settled_episode_transfer \
  --corpus PREDICTIONS.json \
  --execute ced3aa4ee7136bb298ff6a25887a26918cba4ba91e96945a0dc322306a20890f \
  --out /tmp/promptolution-settled-transfer.json
```

Two offline replays produced identical receipts. All 53 focused tests passed, including role isolation, native challenger evaluation, and affordability checks. Storage Guard measured 4.9 GiB free. The disposable source, verified corpus copy, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception and were removed. No provider requests were made. [Tests](../tests/unit/test_promptolution_settled_episode_transfer.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
