# Test smaller validation allowances for later challengers

The full-panel later-first race cleared LMentry's held-out quality gate and saved 7.5% of lookups against the batched GEPA control. The target was 10%. This replay holds the query order, two-pass validation improvement, training reserve, and single qualification attempt fixed. It tests each shorter allowance on six-case validation panels and applies the same fractions, rounded down, to the eight-case ARC-AGI panels. Two further arms cap the allowance at the incumbent's paid validation passes plus two or plus three. [Full-panel result](recorded-certificate-head-to-head.md) · [Replay runner](../benchmarks/recorded_certificate_allowance.py)

| LMentry allowance | Held-out passes | Paid lookups | Saved vs. batched GEPA | Joint paired 95% range | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| One read | 822 | 4,354 | 16.0% | −43 to +3 | Inconclusive |
| Two reads | 822 | 4,419 | 14.7% | −43 to +3 | Inconclusive |
| Three reads | 841 | 4,513 | 12.9% | −23 to +21 | Inconclusive |
| Four reads | 868 | 4,611 | 11.0% | +5 to +46 | Passed |
| Five reads | 880 | 4,701 | 9.3% | +14 to +61 | Failed |
| Six reads | 904 | 4,792 | 7.5% | +38 to +85 | Failed |
| Incumbent passes plus two | 822 | 4,458 | 14.0% | −43 to +3 | Inconclusive |
| Incumbent passes plus three | 841 | 4,569 | 11.8% | −23 to +21 | Inconclusive |

The four-read cap saved 570 lookups against batched GEPA and 635 against sequential GEPA. The controls scored 839 and 833 passes. Relative to the first-certificate policy, 125 of 128 trials kept the same deployment and accounted for 241 of the 257 added lookups. The three improved deployments accounted for the other 16 lookups and all 46 added passes. At six reads, unchanged deployments accounted for 408 of the 438 added lookups. These are net costs that include training and qualification. [Path attribution and all settings](recorded-certificate-allowance-results-v1.json)

The result depends on the homophones task. Across its two model panels, the four-read cap scored 677 passes with 2,138 lookups. Batched GEPA scored 648 passes with 2,803 lookups. On word before, both scored 191 passes and the four-read cap used 95 more lookups. Removing homophones leaves a joint paired range of −7 to +6 and a failed gate. Removing word before leaves a range of +4 to +45 and a passing gate. The per-subject analysis reused the same runs and both GEPA controls.

No other setting cleared both gates. In the eight-challenger rotation, AIME with a one-read cap used 8,191 lookups and reached 4,082 passes, with a joint range of −20 to +38. ARC-AGI with the five-sixths cap used 8,523 lookups and reached 13,783 passes, with a joint range of −37 to +29. BBH still failed the quality gate, and MMLU's paired quality range crossed zero. The LMentry result comes from screening allowances on existing archives. Superiority on newly generated prompts remains unverified.

A follow-up froze the four-read cap on two disjoint model checkpoints. It retained lookup savings and failed the quality gate on disjoint LMentry and BBH tasks. [Frozen transfer comparison](recorded-certificate-allowance-transfer.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. DNS and socket connections were blocked for 38 targeted tests and two byte-identical full replays. The CLI rejected a stale seal. The ordered live plan preview still matched. Storage Guard measured 4.9 GiB free. The temporary export and publication worktree fit the standing 0.2 GiB LAB exception. The replays sent zero provider requests. [Allowance and accounting tests](../tests/unit/test_recorded_certificate_allowance.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_certificate_allowance
python -B -m benchmarks.recorded_certificate_allowance \
  --execute 350b3765cc7dbfb11b32bfa2a708ab33068c761e8949aec6afa3089c5bfc1825 \
  --out NEW_REPORT.json
```
