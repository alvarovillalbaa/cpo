# Qualify the exact nominee without completing both validation scores

The earlier audit found that complete validation scores left only 35 lookups of theoretical savings on original-start ARC-AGI. It found more room when validation only had to identify the exact nominee. This replay tests a selector that uses paid replies to certify that nominee and hands it to the existing independent qualification gate. [Certificate floor](validation-routed-certificate-floor.md) · [Runner](../benchmarks/validation_routed_nominee_certificate.py)

The selector reuses the opening route's paid incumbent grades. For each prompt it tracks observed passes and the highest score it could still attain. It stops when a prompt's paid lower bound beats every rival's upper bound, including roster order on ties and incumbent retention on a tie. A Beta model selects which prompt to read next by minimizing the modeled remaining reads to that decision. Only exact bounds can settle the nominee. For qualification, the primary arm uses the paid validation rates to order checks. The neutral arm starts from equal rates. Both run the same exact independent gate, which can change its read order and stops only when the qualification result is certain.

Both arms run on the same 760 AIME and ARC-AGI episodes and 64 Promptolution episodes as the certificate floor. The benchmark rejects a change to a cycle schedule, nominee, or deployed prompt. It compares actual validation and qualification calls, and prices ARC-AGI calls separately at their recorded historical rates. [Sealed results](validation-routed-nominee-certificate-v1.json)

| Archive | Uncapped passes / lookups | Stall-only passes / lookups | Exact nominee, paid rates | Exact nominee, neutral rates |
| --- | ---: | ---: | ---: | ---: |
| AIME, original | 498 / 601 | 499 / 533 | 498 / 592 | 498 / 594 |
| AIME, rotated | 4,072 / 4,658 | 4,076 / 4,125 | 4,072 / 4,550 | 4,072 / 4,541 |
| ARC-AGI, original | 1,432 / 774 | 1,397 / 610 | 1,432 / 678 | 1,432 / 684 |
| ARC-AGI, rotated | 13,580 / 3,212 | 13,580 / 2,914 | 13,580 / 3,035 | 13,580 / 3,037 |
| Promptolution GSM8K | 2,440 / 850 | 2,436 / 768 | 2,440 / 797 | 2,440 / 804 |
| Promptolution SST5 | 1,439 / 1,598 | 1,441 / 1,336 | 1,439 / 1,539 | 1,439 / 1,524 |

The paid-rate variant removed 537 validation lookups and added 35 qualification lookups, for 502 fewer total lookups across the recorded mix. Neutral rates used the same validation replies and added 28 qualification lookups, for 509 fewer total. Both saved lookups in every group and preserved every deployment. Paid rates used fewer lookups in both ARC-AGI groups. Neutral rates were slightly less expensive at recorded ARC-AGI prices and used seven fewer lookups across the full mix. Neither proof-order estimate consistently reduced cost relative to the other.

On original-start ARC-AGI, paid rates saved 96 of 774 lookups, or 12.4%, and kept all 35 passes lost by stall-only. The paid-rate replay used 68 more lookups than stall-only there. Historical evaluator charges fell from $73.64 to $68.41 on the original start and from $416.67 to $397.01 on rotated starts. At the paid-rate variant's lookup cost, the best affordable GEPA and halving settings trailed it by 201 and 105 passes on the original ARC-AGI start, and by 169 and 164 on rotated starts. All four paired 95% ranges were positive. The AIME control comparisons remained inconclusive. On Promptolution, the paid-rate variant saved 112 lookups relative to uncapped routing. It gained 59 passes over the strongest affordable control, with a paired range of +0.23 to +1.79 percentage points.

Certifying only the nominee recovered some of the cost savings identified by the earlier floor audit while preserving the full-screen outcome. Both variants remain benchmark implementations. Fresh-model performance remains unverified.

## Reproduce offline

Use Python 3.12, the pinned GEPA 0.1.4 wheel, and the original Promptolution corpus. Run without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.validation_routed_nominee_certificate \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 666e75208f7cd7daf5fb6a780e73656895363d3fc7964b5a7e3dccd297981cd0 \
  --out NEW_REPORT.json
```

Two socket-blocked replays matched byte for byte at SHA-256 `2da53d9a75c0a23ff92678e51241b99fc613a248218ae155afa64da2bbf21941`. All 52 focused tests and four subtests passed. They included exhaustive four-case validation panels and every Boolean four-case qualification panel for a fixed certified nominee. The CLI refused a stale seal and existing output. Zero provider requests were sent. Storage Guard measured 9.1 GiB free. The export, GEPA overlay, corpus copy, and publication worktree occupied 124 MiB under the standing LAB exception. [Tests](../tests/unit/test_validation_routed_nominee_certificate.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
