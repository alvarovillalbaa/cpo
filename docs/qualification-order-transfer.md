# Test CPO on unused archived BBH and LMentry model splits

The MMLU cost sweep favored CPO at observed scores and left its paired ranges inconclusive. This study freezes CPO with expected-cost qualification and enrolls archive tasks paired on Airoboros-13B and Nous-Hermes-13B. Neither model appears in the pre-capture CPO correctness inventory. Results for tasks absent from the entire inventory are also reported as a subgroup. [Previous cost sweep](witness-validation-cost-frontier.md) · [Frozen design](qualification-order-transfer-design-v3.json) · [Source archive](https://github.com/SLAB-NLP/Multi-Prompt-LLM-Evaluation#raw-model-responses)

The first capture stopped without writing a correctness snapshot. A check of case IDs and template counts found that both model files for LMentry's word-not-containing task held 26 cases, below the frozen 98-case requirement. The revised design excludes that task in both models and retains all other 44 member identities, the same schedule, candidate, controls, and success rule. No comparison ran before the revision. [Original design](qualification-order-transfer-design-v1.json) · [Revised source](../benchmarks/qualification_order_transfer_v2.py)

The revised capture succeeded. A clean export then exposed a helper that was available locally and absent from Git. The infrastructure amendment includes the original member selection and binary score reduction directly in the published runner. It binds the revised design and snapshot hashes and checks that the scientific settings agree. [Revised design](qualification-order-transfer-design-v2.json) · [Infrastructure amendment](qualification-order-transfer-design-v3.json)

The design pins each enrolled ZIP member by its byte range, uncompressed length, and CRC32 inside the hash-verified directory. Capture reads the enrolled members and preserves binary grader outcomes, ordered case and template IDs, and member digests. The replay uses the established disjoint validation, qualification, and holdout schedules for 32 episodes per model and task. [Runner](../benchmarks/qualification_order_transfer_v3.py) · [Dataset license](../benchmarks/data/bounded-discovery-transfer/LICENSE.cdla-permissive-2.0)

The comparison sweeps sequential and batched GEPA 0.1.4 at paid search caps 20–68. Each search path earns a price under ordinary qualification and the same expected-cost scheduler used by CPO. Archive preflight is unchanged. The replay directly verifies both prices and complete path digests at cap 52 against separate runs of the original adapter. It also checks that CPO's expected-cost order preserves the search and deployment paths.

The primary comparison pools all enrolled tasks. Each of 4,096 paired draws resamples held-out cases within a task and keeps both models and all seeds together. For every draw, the comparator reselects the best affordable fixed GEPA mode, cap, and qualification order at CPO's observed budget. Retaining every start is eligible at zero cost. The candidate passes only with a positive observed advantage and a nonnegative lower paired bound. Separate BBH, LMentry, and previously unseen task results are descriptive.

## Results

CPO passed the pooled archive gate on 44 panels and 660 distinct held-out cases. It scored 18,376 of 42,240 and used 163,285 lookups. The strongest affordable GEPA setting used sequential GEPA with expected-cost qualification at cap 36. It scored 18,021 and used 158,539 lookups. The difference was **355 passes**, with a paired 95% range of **+187 to +520**. [Full results and GEPA sweep](qualification-order-transfer-results-v3.json)

| Cohort | CPO passes / lookups | Best affordable GEPA | GEPA passes / lookups | Pass difference | Paired 95% range |
| --- | ---: | --- | ---: | ---: | ---: |
| All 22 tasks | 18,376 / 163,285 | Sequential, cap 36 | 18,021 / 158,539 | +355 | +187 to +520 |
| BBH | 11,005 / 104,571 | Sequential, cap 36 | 10,856 / 100,834 | +149 | +15 to +278 |
| LMentry | 7,371 / 58,714 | Sequential, cap 36 | 7,165 / 57,705 | +206 | +104 to +305 |
| Two previously unseen tasks | 1,190 / 16,061 | Batched, cap 51 | 1,183 / 14,114 | +7 | −36 to +42 |

Every selected GEPA point in the table uses expected-cost qualification. The cheapest swept GEPA setting to reach CPO's pooled score was sequential at cap 46. It scored 18,432 and used 208,160 lookups, 44,875 more than CPO. Expected-cost ordering reduced CPO's own cost by 2,674 lookups and preserved every search and deployment decision. The new evidence covers fixed archived prompt pools on two model splits absent from the local inventory. The two previously unseen tasks were inconclusive, and fresh-model performance remains unverified.

The public fixed-pool cycle reproduced all 44 CPO panel traces from an installed wheel. [Cycle API and installed replay](expected-cost-cycle.md)

## Reproduce

Use the bundled correctness snapshot, pinned GEPA 0.1.4, and a fresh report path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_order_transfer_v3 \
  --replay benchmarks/data/qualification-order-transfer-v3.json \
  --execute 0c9e1a3f925986b4ef78a7a6de739194149a29479a31e1e0770ca5f18efef720 \
  --out NEW_REPORT.json
```

The independent recapture reproduced the amended snapshot byte for byte. Two offline runs from the published source export produced identical reports with sockets and DNS blocked. They swept 8,624 GEPA panel settings and separately verified 176 cap-52 path and cost receipts against the original adapters. Three focused tests and first- and last-panel smoke checks passed. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 11.6 GiB free. The selected archive ranges transferred 28.8 MB plus the ZIP directory, and the offline scratch overlay used 28.0 MB. Both temporary resources were removed under the standing LAB exception. [Bundled snapshot](../benchmarks/data/qualification-order-transfer-v3.json) · [Verification receipt](qualification-order-transfer-verification-v3.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
