# Compare paid and blind fallback order under a hard budget

A hard shared budget prevented the spending drift seen in the earlier fallback routing replay. At the primary budget, ordering by the incumbent's observed pass fraction improved BBH over both blind ordering and original CPO. The other three families missed the paired gate. [Earlier routing result](witness-fallback-routing.md) · [Sealed results](witness-fallback-reserve-results-v1.json)

Each task first completes the original witness phase. The replay issues a fixed budget from the number of eligible episodes with unused admissions. The primary rate issues eight lookups per eligible episode. Sensitivity rates issue four or twelve. To start a fallback, the remaining credit must cover its full reservation, including all 16 new search lookups and its maximum independent proof. The reservation is 40 lookups for BBH, LMentry, and MMLU, and 32 for Promptolution. The replay settles only the exact paid count and returns unused credit for the next episode. Search and proof stay within the original case splits. [Runner](../benchmarks/witness_fallback_reserve.py)

When a benchmark family is held out, only other families choose the paid ordering and the deterministic blind order. Both methods get the same issued budget per task. The paid order can use observed incumbent passes, total grades acquired during witness screening, or counted challenger wins on paired paid grades. The fit chose ascending incumbent pass fraction in every fold at every rate. The family gate requires positive paired lower endpoints over blind ordering and original CPO at the primary budget.

| Held-out family | Issued lookups | Paid order added passes / lookups | Blind order added passes / lookups | Paired 95% range vs. blind |
| --- | ---: | ---: | ---: | ---: |
| BBH | 1,528 | 105 / 1,219 | 36 / 1,233 | +0.052 to +0.499 pp |
| LMentry | 504 | 41 / 350 | 17 / 352 | 0.000 to +0.410 pp |
| MMLU | 2,696 | 13 / 2,297 | 9 / 2,316 | −0.029 to +0.059 pp |
| Promptolution | 64 | 44 / 38 | 46 / 36 | −0.191 to +0.087 pp |

At the primary rate, paid ordering added 203 passes with 3,904 lookups across the four families. Blind ordering added 108 with 3,937. These are pooled counts across different tasks. The paired gate uses equal task weights within each held-out family. No task exceeded its issued budget. A task with insufficient credit for its first complete reservation made no fallback calls. The single eligible GSM8K episode had eight lookups available against a 32-lookup reservation. The comparisons use archived grades and do not establish model-backed performance. [Per-task settlements and sensitivity](witness-fallback-reserve-results-v1.json)

## Reproduce

Two offline runs produced byte-identical reports. The replay verified the original unconditional cap‑16 costs and gains before fitting any ordering. Eleven targeted tests passed. Tests exercised the full reservation, credit recycling, and outcome-independent ordering. Storage Guard measured 6.0 GiB free, and the disposable export and pinned wheel overlay fit within the standing LAB exception's 0.2 GiB scope. [Tests](../tests/unit/test_witness_fallback_reserve.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.promptolution_witness_capture --out PREDICTIONS.json
python -B -m benchmarks.witness_fallback_reserve \
  --corpus PREDICTIONS.json \
  --execute 9d33053ee180166cffe74c4bce035294967d1d804ed8fc1dbe8fb2787bc34d3c \
  --out FUNDED_FALLBACK.json
```
