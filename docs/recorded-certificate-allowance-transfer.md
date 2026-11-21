# Test the four-read certificate allowance on disjoint archives

Four later-first validation reads beat both matched GEPA controls on the discovery LMentry archive. The advantage depended on homophones. This replay freezes the four-read allowance and uses every panel in the previously published Airoboros-13B and Nous-Hermes-13B archive. Six LMentry and ten BBH tasks are disjoint from the discovery tasks. The other six tasks have the same ordered cases and prompt templates as discovery, with two different model checkpoints. Task identity determines the two groups before any replay. [Discovery result](recorded-certificate-allowance.md) · [Target corpus and provenance](qualification-order-transfer.md)

Each model panel uses the original 32 seeds, eight-challenger rosters, and disjoint panels of ten training, six validation, four qualification, and 30 held-out cases. A later challenger can replace the first nominee only after proving a two-pass validation gain over the incumbent. The policy preserves the training reserve and attempts qualification once. Both GEPA 0.1.4 controls use expected-cost qualification under the same search cap. The replay first reproduces the discovery cohort totals and the four-read comparisons. Each new case resampling draw keeps both models and all seeds together within a task. A cohort passes if the lower endpoint of the joint paired range is nonnegative and paid lookups fall at least 10% against each GEPA control. [Runner](../benchmarks/recorded_certificate_allowance_transfer.py) · [Panel-level receipts](recorded-certificate-allowance-transfer-results-v1.json)

| Target tasks | Four-read CPO | First certificate | Batched GEPA | Sequential GEPA | Joint paired 95% range | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Disjoint LMentry, six tasks | 4,924 / 11,045 | 4,790 / 10,459 | 5,196 / 15,504 | 5,196 / 15,681 | −354 to −216 | Failed |
| Disjoint BBH, ten tasks | 6,544 / 20,468 | 6,485 / 19,655 | 6,644 / 25,843 | 6,748 / 26,434 | −279 to −129 | Failed |
| Original LMentry, two tasks | 699 / 4,568 | 699 / 4,308 | 677 / 5,204 | 671 / 5,178 | −5 to +44 | Inconclusive |
| Original BBH, four tasks | 3,046 / 7,963 | 3,022 / 7,690 | 3,098 / 10,123 | 3,132 / 10,433 | −119 to −53 | Failed |

Each cell gives held-out passes and total paid lookups. On the disjoint LMentry tasks, the extra allowance added 134 passes over the first certificate at a net cost of 586 lookups. It still finished 272 passes behind both GEPA controls. Savings were 28.8% against batched GEPA and 29.6% against sequential GEPA. On disjoint BBH, savings were 20.8% and 22.6%, with a quality deficit against both controls.

On the original homophones and word-before tasks, the four-read policy bought 260 extra replies and changed zero nominees on the two different checkpoints. Both CPO policies scored 699. The full four-read policy saved at least 11.8% against either GEPA control, but the joint range crossed zero. The original four-read gain did not replicate. The archive covers fixed prompt pools, and fresh prompt generation and model performance remain unverified.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and socket connections blocked, 40 targeted tests passed and two full replays matched byte for byte. The CLI rejected a stale seal, and the sealed live plan preview matched. Storage Guard measured 4.8 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replays sent zero provider requests. [Partition and leakage tests](../tests/unit/test_recorded_certificate_allowance_transfer.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_certificate_allowance_transfer
python -B -m benchmarks.recorded_certificate_allowance_transfer \
  --execute 8969936ba35ce69da948ed918fc635002cb251d62fe2db0f637c881430be751b \
  --out NEW_REPORT.json
```
