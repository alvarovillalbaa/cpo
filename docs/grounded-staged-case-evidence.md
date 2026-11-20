# How much does the staged comparison depend on the holdout cases?

The staged archive contains two replies per case for each prompt. This audit replays each archive byte for byte before comparing CPO with the starting prompt and both native GEPA controls. It groups both replies by case ID and keeps them together in every resample. It preserves the number of cases per task and counts all sample combinations with replacement, using integer counts. The table gives the 2.5th and 97.5th percentiles of the resulting total pass difference. The range describes sensitivity to the recorded case mix with the selected prompts held fixed. [Runner](../benchmarks/grounded_staged_case_evidence.py) · [Sealed staged comparison](grounded-staged-comparison.md)

| Panel | GEPA control | Distinct cases | Cases CPO led | Added passes | Central 95% case-resampling range |
| --- | --- | ---: | ---: | ---: | ---: |
| Development | Sequential | 54 | 4 | +8 | +2 to +16 |
| Development | Batched | 54 | 14 | +28 | +16 to +40 |
| Confirmation | Sequential | 24 | 2 | +4 | 0 to +10 |
| Confirmation | Batched | 24 | 7 | +14 | +6 to +22 |

All differences against sequential GEPA came from outage cases. Ticket and warehouse tied on every case. The confirmation comparisons reused the development search costs of 168 CPO calls, 197 sequential GEPA calls, and 174 batched GEPA calls. Each original gate still passed after omitting any one case and its two replies, with thresholds and search costs held fixed. Against sequential GEPA the fixture meets the gate's savings branch, and the confirmation accuracy range includes a tie. The fixture supports reproducible execution. Generalization to fresh model replies remains unverified. [Counts by task and archived hashes](grounded-staged-case-evidence-results-v1.json)

## Reproduce

Create the two archives using the [staged rehearsal commands](grounded-staged-comparison.md#run-the-offline-comparison) and pinned GEPA 0.1.4. The audit also accepts a completed model archive from the same seal. Use its portable `comparison/` directory for each SDK archive. Provider receipts can be checked through the SDK runner before auditing the comparison. The command below checks confirmation against the supplied development archive. Omit `--confirmation` when only development has completed.

```sh
python -B -m benchmarks.grounded_staged_case_evidence \
  --development STAGED_DEVELOPMENT --confirmation STAGED_CONFIRMATION \
  --out CASE_EVIDENCE.json
```

Two offline reports matched byte for byte, and both input archive hash sets matched the original rehearsal. Twelve focused tests passed with sockets and DNS disabled. The verification also checked tamper rejection and refused report paths inside the audited archives. Storage Guard measured 4.5 GiB free. The bounded source export, GEPA wheel overlay, and fixture archives were removed under the standing LAB exception. [Verification receipt](grounded-staged-case-evidence-verification-v1.json) · [Tests](../tests/unit/test_grounded_staged_case_evidence.py)
