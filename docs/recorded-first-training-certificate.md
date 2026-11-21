# Qualify the first challenger with a proved validation gain

The wider backup audit found little recoverable AIME quality after the seeded race had spent its budget. This replay changes the earlier decision. It reads the incumbent's validation panel and walks the original challenger roster. A challenger earns a certificate as soon as its observed passes strictly exceed the incumbent's complete score and preserve every protected critical pass. The race abandons a challenger when the remaining replies cannot prove that gain. It reserves enough budget for a complete validation challenge and the original training check before buying its first reply. [Backup ceiling](recorded-training-veto-backup-ceiling.md) · [Replay runner](../benchmarks/recorded_first_training_certificate.py)

The first-certificate policy then uses the existing conditional proof order and authorizes deployment only after strict gains on the training and independent qualification panels. A control checks training first on the same certificate. The third policy uses that training-first order and can resume the race for a second certificate after a training veto. All arms keep the same roster, precheck, role splits, search cap, and final holdout. Each runs at most one independent challenger qualification. The native GEPA controls use the same verified expected-cost qualification order as the previous study.

| Eight-challenger rotation | Policy | Holdout passes | Paid lookups |
| --- | --- | ---: | ---: |
| AIME | Seeded CPO | 4,073 | 12,164 |
| AIME | First certificate | 4,082 | 8,191 |
| AIME | First certificate, training first | 4,082 | 8,805 |
| AIME | Allow second certificate after training veto | 4,076 | 10,835 |
| AIME | Sequential GEPA | 4,074 | 13,701 |
| AIME | Batched GEPA | 4,055 | 13,397 |
| ARC-AGI | Seeded CPO | 13,822 | 9,896 |
| ARC-AGI | First certificate | 13,755 | 8,346 |
| ARC-AGI | First certificate, training first | 13,755 | 8,988 |
| ARC-AGI | Allow second certificate after training veto | 13,813 | 10,448 |
| ARC-AGI | Sequential GEPA | 13,785 | 11,880 |
| ARC-AGI | Batched GEPA | 13,781 | 10,702 |

On AIME with eight challengers, the first-certificate policy saved 3,973 lookups and gained nine passes against seeded CPO. It stopped on a partial validation certificate in 73 of 224 nominations. It used 40.2% fewer lookups than sequential GEPA and 38.9% fewer than batched GEPA, with observed gains of eight and 27 passes. The joint paired case sensitivity range against GEPA was −20 to +38, so the joint gate remained inconclusive. The training-first control reproduced the same deployments, and the second-certificate policy added 2,644 lookups and lost six net passes relative to first certificate. [All settings, ranges, and proof counts](recorded-first-training-certificate-results-v1.json)

On ARC-AGI with eight challengers, the first-certificate policy used 1,550 fewer lookups than seeded CPO and lost 67 passes. The second-certificate policy recovered 58 of those passes at a cost of 2,102 more lookups. The first-certificate policy also lost 82 passes against seeded CPO on the original ARC start in the eight-challenger run. These results support a lower-cost AIME candidate for further testing. The same rule did not transfer its quality to ARC, and the archive supplies no fresh model replies.

A follow-up froze the rule on 26 MMLU, BBH, and LMentry model panels. It saved lookups on all three cohorts and scored fewer held-out passes than both GEPA controls on each. [Cross-cohort transfer](recorded-first-certificate-transfer.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 28 targeted tests passed and two replays matched byte for byte. Tests enumerated all 512 outcome matrices for a three-case validation pool with a protected case. The seeded CPO and both GEPA traces reproduced on all 1,520 trials. The CLI rejected a stale seal, and the ordered live plan reproduced. Storage Guard measured 5.9 GiB free. The 39 MiB source export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Certificate tests](../tests/unit/test_recorded_first_training_certificate.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_first_training_certificate
python -B -m benchmarks.recorded_first_training_certificate \
  --execute c261acb13200b8f297fe37ad08f12a4e98fb1eb21efe81eb62814ad46f12715b \
  --out NEW_REPORT.json
```
