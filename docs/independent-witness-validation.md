# Check for a validation gain beyond the screening case

The funded finalist retry found more validation winners and barely changed held-out accuracy. A narrow-search finalist enters the race by repairing its screening case. That same repair also counts toward its strict validation gain. This replay tests whether requiring evidence from the rest of the validation panel improves deployment. [Funded retry](funded-finalist-retry.md)

- **Second repair** requires at least one other case that the challenger passes and the incumbent misses.
- **Independent gain** requires a strictly positive net gain across the validation panel after removing the screening case. Losses elsewhere in that panel can offset a second repair.

Both policies first run the original narrow search. They reuse every paid reply and only finish the missing evidence needed to decide the extra condition. The existing reserve already funds the incumbent and finalist on the entire panel. A veto leaves the incumbent in place. A successful check still goes through the same fresh qualification. Wide search and archive preflight retain their original gates. [Replay runner](../benchmarks/independent_witness_validation.py)

The retrospective comparison uses 32 four-cycle episodes on each of 44 archived model and subject panels. It shares the original case splits and lookup caps with strict CPO and the published cap-52 GEPA controls. The combined gate requires at least 10% fewer paid lookups and a nonnegative lower endpoint of the joint central 95% paired accuracy range against both GEPA controls. [Source protocol](funded-finalist-retry.md)

## Results

Each cell gives total holdout passes and paid lookups.

| Method | Llama and Mistral | Gemma and Flan | Mixtral and Falcon |
| --- | ---: | ---: | ---: |
| Original CPO | 17,724 / 49,330 | 17,435 / 35,496 | 29,616 / 46,981 |
| Second repair | 17,697 / 44,654 | 17,421 / 32,126 | 29,599 / 41,550 |
| Independent gain | 17,697 / 43,556 | 17,425 / 31,696 | 29,591 / 40,861 |
| Batched GEPA, cap 52 | 17,694 / 57,271 | 17,422 / 40,184 | 29,600 / 53,024 |
| Sequential GEPA, cap 52 | 17,721 / 81,537 | 17,409 / 60,951 | 29,625 / 77,567 |

Second repair vetoed 711 of 1,090 narrow-search finalists. The original validation replies resolved every check. This arm saved 13,477 lookups across the three cohorts and lost 58 holdout passes relative to CPO. Independent gain vetoed 827 of 1,090 finalists and needed 282 additional validation replies to decide the checks. The whole replay saved 18,148 qualification lookups and used 2,454 more search lookups. Its net savings were 15,694 lookups, with 62 fewer holdout passes. [Per-panel outcomes and paid costs](independent-witness-validation-results-v1.json)

Both variants cleared the 10% savings requirement against both cap-52 GEPA controls. The independent-gain arm saved 23.9%, 21.1%, and 22.9% against batched GEPA. Its joint paired accuracy ranges were −83 to +28, −47 to +50, and −102 to +29 passes. All six variant-by-cohort gates were inconclusive. [Paired ranges](independent-witness-validation-results-v1.json)

For cost context, the second-repair arm gained ten passes and saved 1,025 lookups against the previously published cap-47 batched GEPA point on Llama and Mistral. On Mixtral and Falcon it gained 15 passes and saved 125 lookups. On Gemma and Flan it gained 14 passes and used 518 more lookups. These are descriptive comparisons against one lower-cost setting. The evidence leaves the original CPO selector in place. [Llama and Mistral cap 47](routed-score-allocation.md) · [Gemma and Flan cap 47](posterior-model-transfer.md) · [Mixtral and Falcon cap 47](late-miss-transfer.md)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path. Preview the seal before running the benchmark.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.independent_witness_validation
PYTHONHASHSEED=0 python -B -m benchmarks.independent_witness_validation \
  --execute 709469335d604fdb22f5ae441a4945b3d37352664cbadfaa55093ab984fd9407 \
  --out NEW_REPORT.json
```

Two clean-source replays matched byte for byte with sockets and DNS blocked. They reproduced all 132 published control-panel records. Three focused tests checked 1,536 combinations of binary outcomes, rules, and caps. They verified outcome parity with the complete validation predicate, retained critical-pass protection, and checked unique lookup accounting. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 11.8 GiB free. The 22.3 MB scratch overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_independent_witness_validation.py) · [Verification receipt](independent-witness-validation-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
