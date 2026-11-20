# Test the tie extension on BBH and LMentry

Extending qualification only when the first four cases tied improved CPO on three previously examined MMLU cohorts. This follow-up published the candidate, controls, task and model roster, and acceptance gate before extracting any selected score member. The design commit is `ef2231477b0ad7afe12a95ed9ea8e596de423a6e`. [MMLU replay](qualification-role-transfer.md) · [Frozen design](tie-extension-cross-benchmark-design-v1.json)

The BBH tasks are movie recommendation, ruin names, salient translation error detection, and snarks. LMentry contributes homophones and word before, which appeared on other model splits in prior studies. All six tasks use Falcon-7B-Instruct and MPT-7B-Instruct. The four BBH task configurations and all 12 task and model combinations were absent from the 156 combinations in the local captured inventory. The snapshot stores ordered case and template IDs, binary grader outcomes, and a hash and ZIP checksum for each selected source member. [Authors' raw response archive](https://github.com/SLAB-NLP/Multi-Prompt-LLM-Evaluation#raw-model-responses) · [CDLA license](../benchmarks/data/bounded-discovery-transfer/LICENSE.cdla-permissive-2.0) · [Reduced snapshot](../benchmarks/data/tie-extension-cross-benchmark-v1.json)

Every method uses the same 32 seeded four-cycle episodes per panel, starts, proposal blocks, disjoint 12-case validation panels and eight-case qualification reservations, and paid search cap of 52. Both official GEPA 0.1.4 modes use eight cases in their original arms and the same tie extension as CPO in the matched arms. A proven four-case gain or loss ends the shorter comparison. A tie reads the remaining four cases. Archive challenger reads still debit the cycle's search budget. Each of 4,096 draws resamples the 180 distinct final holdout cases within subject, keeping both models and all episodes together. To pass, CPO must save at least 10% of lookups against all four GEPA controls and have a nonnegative lower endpoint for the central 95% range of the smallest pass difference across them. [Runner](../benchmarks/tie_extension_cross_benchmark.py)

## Results

| Setting | Holdout passes / 11,520 | Paid lookups |
| --- | ---: | ---: |
| Retain start | 2,475 | 0 |
| CPO, eight cases | 3,304 | 34,647 |
| CPO, extend ties | 3,282 | 31,490 |
| Batched GEPA, eight cases | 3,396 | 47,537 |
| Batched GEPA, extend ties | 3,398 | 44,572 |
| Sequential GEPA, eight cases | 3,457 | 65,252 |
| Sequential GEPA, extend ties | 3,421 | 60,853 |

Tie-extension CPO used 29.4% to 51.7% fewer lookups than the four GEPA controls and scored 114 to 175 fewer passes. It beat both eight-case GEPA controls on homophones and scored lower on the other five tasks. The simultaneous paired range was **−284 to −83 passes**, and the frozen gate **failed**. The range describes sensitivity to the archived cases, conditional on these tasks and trajectories. [Sealed panel results](tie-extension-cross-benchmark-results-v1.json)

Compared with eight-case CPO, the candidate saved 3,157 lookups and scored 22 fewer passes. Its paired range against that CPO control was −54 to +10. Snarks and homophones accounted for 23 lost passes before gains on other tasks. The eight-case default remains in place.

A search follow-up found 110 comparisons where CPO missed a candidate that would have passed both gates on its offered cycle. [Two-finalist validation race](balanced-finalist-race.md)

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. The committed corpus is sufficient for replay.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.tie_extension_cross_benchmark \
  --replay benchmarks/data/tie-extension-cross-benchmark-v1.json \
  --execute 192ccff87150efe40aae245d35c56864cfde05dff0bd8ae4a74b59c4df37b18f \
  --out NEW_REPORT.json
```

The selected ZIP ranges and both directory reads totalled 7,560,513 bytes. Every range matched the pinned source length and ETag, and the directory matched its SHA-256. Python checked each selected member's ZIP checksum at extraction. Two extractions and two replays with sockets and DNS blocked matched byte for byte. Five focused tests passed, and a stale seal was rejected before output creation. Storage Guard measured 15.5 GiB free. The standing LAB exception covered the bounded capture and replay files, which were removed. Fresh prompt generation and provider costs remain unverified.
