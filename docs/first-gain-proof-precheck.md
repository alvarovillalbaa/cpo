# Test qualification before terminal validation

The 18-read first-gain policy still spent 945 more lookups than the strongest affordable native GEPA setting on rotated AIME. This replay asks whether the last cycle can skip validation when paid independent qualification grades already prove that neither challenger could deploy. It keeps the 760 math episodes, 64 Promptolution episodes, rosters, cases, and held-out grading from the package comparison. [First-gain math results](certified-strict-gain.md) · [Three-cycle results](certified-strict-gain-transfer.md)

The precheck applies to the final uniform cycle with two challengers and four noncritical qualification cases in one family. It pays the usual incumbent qualification prefix, then orders further reads by the modeled probability of proving both rejections within the cap. For each challenger the greatest possible gain is four minus the incumbent's known passes and that challenger's known failures. Validation can stop when both upper bounds reach zero. If the precheck cannot establish that result, the original selector runs and reuses exact paid qualification replies. Qualification grades never change which challenger the fallback nominates.

The replay checks every preceding cycle decision and the final deployed prompt against the packaged 18-read policy. It tests precheck caps of eight and twelve, with or without a trigger of two passes in the usual incumbent prefix. The eight-read variant with that trigger was the primary comparison. The twelve-read variants are sensitivity checks. The proof phase can use up to 12 distinct replies across the three prompts. [Runner](../benchmarks/first_gain_proof_precheck.py) · [Sealed receipt](first-gain-proof-precheck-v1.json)

## Results

Holdout passes were identical across all policies within each group. The remaining columns show paid lookups.

| Archive | Held-out passes | Packaged baseline | 8 after two passes | 12 after two passes | 12 without a trigger |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIME original | 499 | 552 | 561 | 529 | 520 |
| AIME rotated | 4,080 | 4,282 | 4,271 | 3,980 | 3,789 |
| ARC-AGI original | 1,439 | 614 | 618 | 618 | 680 |
| ARC-AGI rotated | 13,578 | 2,987 | 2,998 | 2,869 | 2,903 |
| Promptolution GSM8K | 2,436 | 786 | 794 | 803 | 813 |
| Promptolution SST-5 | 1,441 | 1,392 | 1,402 | 1,374 | 1,339 |

On rotated AIME, the unrestricted twelve-read precheck saved 493 lookups, or 11.5%. The best affordable native GEPA setting scored 4,072 in 3,337 lookups, leaving a 452-lookup gap. A hindsight certificate using only the most favorable sufficient replies could have saved up to 1,386 lookups across 149 uniform episodes in which neither challenger qualified. This ceiling leaves the remaining episodes at baseline cost and omits the cost of discovering which replies will certify rejection.

On rotated ARC-AGI, the twelve-read rule with the trigger saved 118 lookups and lowered replayed evaluator charges from $390.66 to $374.61. The same rule added four lookups on original ARC-AGI, where the replay found zero uniform episodes with two proof-ineligible challengers. In Promptolution, the unrestricted twelve-read version saved 53 lookups on SST-5 and added 27 on GSM8K. The strongest affordable native and halving comparisons are repriced from the published point totals. The replay uses shared recorded prompts and leaves fresh-proposal performance unmeasured.

## Reproduce offline

Use Python 3.12 and the original hash-pinned Promptolution corpus. Run without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_proof_precheck \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute fd6b935bf0e4210158b31ef2d24ee10b380f5ffd8f5943befda85b87c3b84e24 \
  --out NEW_REPORT.json
```

Both socket- and DNS-blocked replays produced byte-identical receipts at SHA-256 `74051c3bef57474309a37fc7fbdf8516b2b31ddea3013bbd080f3800313132c3`. All 19 focused tests passed. The tests checked every Boolean four-case grading board and verified that a challenger with stronger qualification cannot replace the fallback validation nominee. The CLI refused a stale seal, an occupied output path, and an incorrect corpus. Storage Guard measured 8.4 GiB free. The isolated export, corpus and publication worktree occupied 126 MiB under the standing LAB exception. Zero provider requests were sent. [Tests](../tests/unit/test_first_gain_proof_precheck.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
