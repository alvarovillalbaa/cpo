# Run the exact validation certificate inside the repair cycle

Set `certify_final_draft=True` on `run_validation_guided_repair_cycle` to stop the final draft's validation as soon as the decision is settled. The cycle uses the fully scored opening and any cached final-draft replies. The same strict gain, family nonregression, and protected critical-pass rule determines acceptance. The full validation allowance is reserved before the final draft, and independent qualification still compares the resulting nominee with the incumbent. Full validation remains the API default. [Repair cycle](../cpo/validation_guided_repair.py) · [Certificate](../cpo/anchored_validation.py)

The integrated replay called the evaluator directly and checked recorded search counts against callback counts. It reproduced the prior exact savings on 144 previously studied panel and fault-mode combinations. A separate cohort used 36 disjoint input panels in each of two fault modes. Both native GEPA 0.1.4 controls received the same search cap, shared opening, and adaptive qualification schedule. [Runner](../benchmarks/opening_validation_certificate_transfer.py)

| Fresh fixture method | Original faults passes / calls | Shifted faults passes / calls |
| --- | ---: | ---: |
| CPO with certificate | 648 / 2,239 | 648 / 2,244 |
| CPO with full validation | 648 / 2,268 | 648 / 2,275 |
| Sequential GEPA | 571 / 2,528 | 561 / 2,484 |
| Batched GEPA | 537 / 2,276 | 518 / 2,287 |

The certificate saved 29 and 31 actual fixture evaluation callbacks, with the same repair decisions, qualification counts, and holdout outcomes as full validation. It cleared both GEPA gates in both modes with zero matched critical losses. The sealed test covers deterministic fixture replies. Provider costs and fresh model quality remain unverified. [Sealed results](opening-validation-certificate-transfer-results-v1.json)

## Reproduce offline

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_validation_certificate_transfer \
  --execute e2a9d7d479013c39bc2679c5e23e61d468aaf08a24321807c54618d7d0e53b1f \
  --out NEW_REPORT.json
```

Use pinned GEPA 0.1.4 and a fresh report path. Two source replays and one installed-wheel replay matched byte for byte. Twelve focused tests passed with sockets and DNS disabled. Storage Guard measured 4.6 GiB free. The 30.7 MB bounded overlay was removed under the standing LAB exception. [Verification receipt](opening-validation-certificate-transfer-verification-v1.json)

The opt-in changes the repair module's source SHA-256 from `4f71160b978a4ef39dce40ac5e8153947586bc5f4a075174adb849c8ae16b349` to `e99b6362aab2ba3d60bfb5c93b3f6374b75891d94001db08ab75d4d726c33029`. Historical replays use their original Git revisions. Both original staged fixture archives matched their published hashes, and the original pinned Luna SDK launcher reproduced its saved development plan byte for byte. [Historical staged replay](grounded-staged-comparison.md#run-the-offline-comparison)

A follow-up reordered final validation within the exact certificate. It saved 32 reads on new scripted panels and matched all 240 recorded Sol traces after retaining the original order when only one net gain remained possible. [Family-ordered validation](opening-final-validation-order.md)
