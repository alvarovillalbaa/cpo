# Screen a paid candidate on a known incumbent miss

The no-nominee benchmark found independently qualifying improvements that its paid validation rules rarely selected. This replay keeps the original search and the supported-rate candidate fixed. After a no-nominee stop, it offers that candidate one unanswered validation case from its own cycle where the incumbent already failed. A passing probe opens the candidate's original independent proof. A failing probe retains the incumbent. The new grade uses one lookup from the 24-lookup proof allowance. [No-nominee comparison](witness-no-nominee-admission.md) · [Runner](../benchmarks/witness_no_nominee_miss.py)

The first arm uses the earliest eligible case in the schedule. The second favors cases where other already-evaluated prompts have a higher smoothed pass rate, breaking ties in scheduled order. Both use only paid validation at the time they choose. A direct control sends the same candidate to proof on the same eligible episodes with a 23-lookup cap. The full supported-rate policy retains its original 24-lookup proofs for comparison. Each arm pays for every validation and proof reply it actually reads.

The other benchmark family chooses among the declared policies by promotion count within original seeded spend, with lower cost breaking ties. Transfer requires a positive paired lower endpoint against the full single proof and cost within the seeded proof allowance in every cohort.

## Results

| Cohort | Eligible probes | Passes, scheduled / peer order | Direct cap-23 passes / lookups | Scheduled probe passes / lookups | Peer probe passes / lookups |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 82 | 8 / 9 | 17,146 / 72,121 | 17,076 / 71,245 | 17,092 / 71,268 |
| MMLU prior subjects | 19 | 0 / 0 | 21,203 / 34,437 | 21,180 / 34,141 | 21,180 / 34,141 |
| MMLU additional subjects | 3 | 0 / 0 | 8,976 / 13,692 | 8,976 / 13,642 | 8,976 / 13,642 |

All 22 supported-rate MMLU candidates had an eligible miss. The two orders chose different cases in 11 episodes. Every probed candidate failed, so neither arm opened an independent proof or changed the incumbent. The direct cap-23 control promoted five candidates on the prior subjects and added 23 pooled passes. It exceeded seeded spend on the prior subjects by 94 lookups.

On BBH and LMentry, peer ordering saved 853 lookups and lost 54 held-out passes against the matched direct control. The paired range was −0.246 to −0.033 percentage points. Both training families selected an existing control, and the cross-family gate remained unmet. [Full costs and paired comparisons](witness-no-nominee-miss-results-v1.json)

## Reproduce

Use a clean export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 48 targeted tests passed and two replays matched byte for byte. The original no-nominee counts, candidate selection counts, and control costs and scores reproduced. The CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 3.9 GiB free. The export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Probe accounting tests](../tests/unit/test_witness_no_nominee_miss.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_no_nominee_miss
python -B -m benchmarks.witness_no_nominee_miss \
  --execute 35ee77c25b7fcf2d2af123a8ede9659de3517361325c1d83fec495f075534718 \
  --out NEW_REPORT.json
```
