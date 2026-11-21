# Use the other prompt's reply to order a proof

Peer-model scores changed 39 deployments and produced no reliable held-out gain. This comparison tests evidence from the current episode. It keeps paid search, the first proof, the selected rival, the second-proof panels, and the remaining allowance fixed for 1,066 archived second attempts. [Peer-model comparison](witness-peer-case-order.md) · [Runner](../benchmarks/witness_same_case_order.py)

Both experimental arms estimate how likely a read is to tighten the promotion or rejection bound. They start each side with its own smoothed validation rate and update from the proof replies actually read. When one side of a case is known, the conditional arm estimates the other side's pass rate from completed pairs with the same known reply. It pools matching pairs from the current paid search and proof and shrinks that estimate toward the marginal rate using four prior observations. The marginal control uses the same scheduling rule and ignores the other side of the case when estimating a pass rate.

These estimates only order reads. The observed score bounds determine the result. A tie opens the reserve only after both base sides are complete. The pair order may change within each panel while case membership and the cap stay fixed. The comparison requires a positive paired lower endpoint against both the original expected-read policy and the marginal-only control, with total spend within the original seeded single-proof cost on every cohort.

## Results

| Cohort | Expected-read order passes / lookups | Marginal-only passes / lookups | Conditional passes / lookups | Conditional vs expected-read paired 95% range, percentage points |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,121 / 75,764 | 17,133 / 75,885 | 17,164 / 75,868 | −0.002 to +0.220 |
| MMLU prior subjects | 21,174 / 35,910 | 21,174 / 35,927 | 21,175 / 35,890 | −0.005 to +0.016 |
| MMLU additional subjects | 8,989 / 14,759 | 8,984 / 14,768 | 8,979 / 14,749 | −0.183 to +0.046 |

The same-case signal added 27 passes and saved 73 lookups against the marginal-only scheduler across the three cohorts. Relative to the original expected-read order, it changed 23 deployments, added 13 rival promotions, gained 43 passes on BBH and LMentry, and lost nine passes on pooled MMLU. It spent 74 additional lookups overall. Every paired range included zero, and every cohort exceeded the seeded single-proof cost. The policy failed the transfer gate. [Full report and paired ranges](witness-same-case-order-results-v1.json)

## Reproduce

Use a clean source export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 38 targeted tests passed and two full replays matched byte for byte. The tests check all 256 combinations of base and reserve grades on two rows each, with both schedulers and three caps. All comparison panel traces matched, the CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 4.9 GiB free. The source export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Exact gate tests](../tests/unit/test_witness_same_case_order.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_same_case_order
python -B -m benchmarks.witness_same_case_order \
  --execute 767f5670ba0242604177ba8d1f8b24065b371eeeb2d10bc1383db93935d4417d \
  --out NEW_REPORT.json
```
