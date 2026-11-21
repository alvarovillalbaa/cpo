# Compare later challengers with the first certified prompt

The pruned lookahead can replace a first certified prompt when a later challenger shows a two-pass validation gain over the incumbent. It can spend some of the allowance extending the first prompt's certificate before checking the later roster. This replay tests two changes at the original one- and two-panel allowances. [Pruned lookahead](recorded-certificate-lookahead-pruning.md)

- **Later challengers first.** Check later prompts in roster order for the same two-pass lower bound over the incumbent. Keep the first prompt as the fallback.
- **Head-to-head proof.** Apply the same incumbent check, then require a strict gain over the first prompt, no validation family losses, and preservation of its critical passes. Both checks use the same lookup allowance. Skip the paired proof when even favorable replies cannot settle it with the remaining allowance.

Both versions preserve the candidate's training reserve and use a single qualification attempt. They replay the same 2,352 archived trials per arm and reproduce the published pruned reference totals and comparisons. Held-out replies are read after the simulated search has selected and qualified its prompt. [Runner](../benchmarks/recorded_certificate_head_to_head.py) · [Full report](recorded-certificate-head-to-head-results-v1.json)

| Setting | Pruned lookahead, one panel | Later first, one panel | Head-to-head, one panel | Pruned lookahead, two panels | Later first, two panels | Head-to-head, two panels |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIME, eight-challenger rotation | 4,077 / 8,692 | 4,078 / 8,832 | 4,077 / 8,821 | 4,076 / 9,461 | 4,075 / 9,776 | 4,072 / 9,830 |
| ARC-AGI, eight-challenger rotation | 13,777 / 8,586 | 13,765 / 8,873 | 13,766 / 8,774 | 13,778 / 8,941 | 13,755 / 9,455 | 13,762 / 9,580 |
| MMLU | 13,434 / 10,979 | 13,434 / 11,007 | 13,434 / 10,987 | 13,434 / 11,661 | 13,434 / 11,688 | 13,434 / 11,686 |
| BBH | 2,054 / 8,619 | 2,053 / 8,755 | 2,054 / 8,705 | 2,054 / 9,275 | 2,066 / 9,540 | 2,054 / 9,560 |
| LMentry | 857 / 4,693 | 904 / 4,792 | 857 / 4,737 | 889 / 4,977 | 903 / 5,241 | 901 / 5,247 |

Each cell gives held-out passes and paid lookups. On LMentry, testing later challengers first with one panel added 47 passes for 99 more lookups. Its joint held-out gain over the two GEPA controls ranged from +38 to +85 passes in the case resampling analysis. The arm saved 7.5% versus batched GEPA and needed 130 fewer lookups to reach 10%. The one-panel head-to-head rule lost the 47-pass gain and still missed the cost gate. The two-panel head-to-head rule reached 901 passes with a +38 to +80 quality range, at 1.3% more lookups than batched GEPA.

Across the 11 settings, none of the four new arms met both the quality and cost gates. The eight-challenger rotations of AIME and ARC-AGI still left held-out quality inconclusive. BBH's best new arm gained 12 passes and passed the cost gate, while its case resampling range remained below zero against the two GEPA controls. MMLU held-out totals stayed fixed. The extra comparison proof did not justify adopting either allowance.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and socket connections blocked, 33 targeted tests passed and two replays matched byte for byte. The CLI rejected a stale seal, and the sealed ordered live plan preview still matched. The replays sent zero provider requests. Storage Guard measured 4.8 GiB free and the bounded export used the standing LAB storage exception. [Targeted tests](../tests/unit/test_recorded_certificate_head_to_head.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_certificate_head_to_head
python -B -m benchmarks.recorded_certificate_head_to_head \
  --execute 1a3807fac78666889a1c907b30914459d8b4693045187ebd79d62613d6ecdb1e \
  --out NEW_REPORT.json
```
