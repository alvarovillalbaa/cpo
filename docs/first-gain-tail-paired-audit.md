# Audit when wider validation helps CPO

The first-gain widening study reported held-out pass counts across reruns of the same archived questions. This audit groups all appearances of a held-out question and resamples those groups together. Each draw uses the same question weights for all policies. It compares the six-read and nine-read extensions with fixed three-case CPO, the prior full-panel terminal policy, and every previously enrolled native GEPA or halving setting affordable under either candidate's realized budget. The strongest affordable GEPA and halving scores are selected again in each draw. Lookup costs and recorded ARC-AGI prices stay fixed. The audit reproduced the earlier layouts, observed scores, and costs and verified that every CPO promotion had a positive independent qualification margin. [Widening study](first-gain-validation-tail.md) · [Native GEPA sweep](certified-nomination-gepa-sweep.md) · [Audit runner](../benchmarks/first_gain_tail_paired_audit.py)

## Archived comparisons

Cells show the observed pass difference and the middle 95% range from 4,096 paired question resamples. GEPA and halving comparisons use the six-read policy's realized lookup ceiling. Positive values favor the six-read policy. The reference comparators and the native settings run offline on shared, recorded prompts. These are individual ranges that describe question sensitivity within the archive.

| Archive | Distinct questions | Six reads vs fixed three | Six reads vs native GEPA | Six reads vs halving |
| --- | ---: | ---: | ---: | ---: |
| AIME original | 45 | 0 [0, 0] | −3 [−30, +16] | −4 [−30, +7] |
| AIME rotated | 45 | +4 [−6, +14] | +4 [−42, +40] | +7 [−35, +30] |
| ARC-AGI original | 80 | +32 [+23, +41] | +225 [+174, +275] | +142 [+108, +175] |
| ARC-AGI rotated | 80 | +24 [+16, +32] | +104 [+76, +132] | +99 [+73, +125] |
| Promptolution GSM8K | 90 | +25 [+10, +40] | +187 [+109, +267] | +13 [−1, +27] |
| Promptolution SST-5 | 90 | −27 [−47, −7] | +206 [+108, +301] | +10 [−14, +34] |

The positive ARC-AGI ranges against GEPA and halving held under both lookup and historical-price ceilings. The nine-read policy also had positive ranges against both controls on ARC-AGI and GSM8K. On GSM8K, its lead over halving was 45 passes with a range of +17 to +73. It tied the previous terminal policy on every resampled GSM8K question and used 71 fewer lookups. Both extensions' AIME ranges included zero against native GEPA. On SST-5 the six-read extension lost passes against the fixed three-case policy while using 120 more lookups. The independent value of widening varies by archive, and performance with fresh model proposals remains unverified. [Sealed question vectors and comparisons](first-gain-tail-paired-audit-v1.json)

## Reproduce offline

Use Python 3.12, the hash-pinned GEPA 0.1.4 wheel, and the reduced Promptolution corpus bound by the receipt. Run without arguments to print the plan seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_tail_paired_audit \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 2b3f2dbdbe5d3288797ae3350810ecb57c1286f20c73ecfa17a53ef3f08c4901 \
  --out NEW_REPORT.json
```

Two full runs blocked sockets and DNS and produced byte-identical receipts at SHA-256 `1a72ac584ddffb9ff81b492be83ddb789587e53f39c18f2ac267c971f757f617`. All 37 focused tests passed, including repeated-question pairing, control reselection, and affordability by either cost axis. The CLI refused a stale seal, an existing output path, and an incorrect corpus. Storage Guard measured 8.3 GiB free. The source export, wheel overlay, and publication worktree fit within 0.16 GiB under the standing LAB storage exception. Zero provider requests were sent. [Tests](../tests/unit/test_first_gain_tail_paired_audit.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
