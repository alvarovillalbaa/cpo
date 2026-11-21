# Confirm the two-witness shortlist on different archived checkpoints

The two-witness shortlist led at matched cost on the six LMentry tasks used to refine it. This replay freezes that policy and uses all 32 archived Flan-T5-XL and Minotaur-15B panels. Neither checkpoint was in the shortlist study. Fourteen tasks were previously examined on other models and retain the same ordered cases and prompt templates. BBH causal judgment and LMentry ends-with-word were outside the shortlist study. Each has two model panels. [Policy and earlier results](recorded-shortlist-screen-order.md) · [Binary archive snapshot](../benchmarks/data/shortlist-model-transfer-v1.json)

The snapshot is a byte-for-byte copy of the independently captured reduced correctness archive. It contains binary outcome matrices and their case, template, model, and source identities. Its recorded parent ZIP SHA-256 is `c897e7ef69561578c469059d870169615d822ba9415c8a5e68399ddb875d8cbe`. [Source archive](https://github.com/SLAB-NLP/Multi-Prompt-LLM-Evaluation#raw-model-responses) · [Data license](../benchmarks/data/bounded-discovery-transfer/LICENSE.cdla-permissive-2.0)

The replay keeps all 32 seeds, eight-challenger rosters, six validation cases, training reserve, and separate four-case qualification. It compares the fixed two-witness shortlist and the older fixed-halves policy with sequential and batched GEPA 0.1.4 at each integer cap from 6 to 180. The best affordable fixed GEPA setting is selected again on every paired draw, retaining both models and all seeds for sampled cases within each task. [Runner](../benchmarks/recorded_shortlist_model_transfer.py) · [All settings, comparisons, and panel receipts](recorded-shortlist-model-transfer-results-v1.json)

| Target cohort | Two-witness passes / lookups | Best affordable GEPA passes / lookups | Paired margin and 95% range | Fixed-halves margin and range |
| --- | ---: | ---: | ---: | ---: |
| Previous LMentry tasks, six | 5,524 / 10,951 | 5,338 / 10,475 | +186, +117 to +235 | +144, +80 to +197 |
| Previous BBH tasks, eight | 4,904 / 14,535 | 4,775 / 13,677 | +129, +77 to +174 | +102, +56 to +145 |
| Disjoint LMentry ends-with-word | 349 / 2,127 | 340 / 2,114 | +9, −3 to +20 | +34, +21 to +45 |
| Disjoint BBH causal judgment | 638 / 1,738 | 596 / 1,620 | +42, +23 to +61 | +30, +16 to +44 |

On the previously examined tasks, the least expensive GEPA settings reaching the two-witness score used 2,534 more lookups on LMentry and 4,382 more on BBH. Both checkpoints contributed to the observed gains at the pooled best affordable GEPA settings. Minotaur-15B accounted for 147 of the 186 LMentry passes and 118 of the 129 BBH passes gained over those settings. It accounted for all 42 passes gained on causal judgment. On ends-with-word, the two CPO policies reached the same score and fixed halves spent 108 fewer lookups. The task transfer includes one new task per benchmark, and the paired ranges describe sensitivity to their archived cases. Fresh prompt generation remains unverified.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, 52 targeted tests passed and two full replays matched byte for byte. The runner reproduced both CPO path hashes on one tuning panel per cohort and both original-cap GEPA paths on each target panel. Direct replay independently matched seven reported GEPA settings across 1,984 archived trials. The CLI rejected a stale seal, and the ordered live plan preview matched. Storage Guard measured 4.8 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests. [Confirmation partition tests](../tests/unit/test_recorded_shortlist_model_transfer.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_shortlist_model_transfer
python -B -m benchmarks.recorded_shortlist_model_transfer \
  --execute f779a9f955c1114af4eaf44fc4987b0139408fec91cebd6d81e2f2849e8e238d \
  --out NEW_REPORT.json
```
