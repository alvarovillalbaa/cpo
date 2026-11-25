# Transfer first-gain certification to three-cycle optimization

The math replay found that a validation screen could stop as soon as any challenger proved a strict full-panel gain. The 18-read variant reduced spend against exact nomination on AIME and ARC-AGI. This test transfers that variant and the 14-read sensitivity to 32 GSM8K and 32 SST-5 episodes. It keeps the original ordered rosters, six validation cases and four independent qualification cases per cycle, and 90 held-out questions per task. [Math replay](certified-strict-gain.md) · [Original control sweep](certified-nomination-gepa-sweep.md)

Each episode has three cycles. A challenger becomes the incumbent only after independent qualification. A rejected nomination can change the next cycle's schedule. The replay verifies each deployment against the actual incumbent and its own disjoint qualification panel. It checks all previous score and lookup totals and retains the 128 native GEPA settings, five halving settings, and retention.

The usual pooled comparison uses one setting across both tasks. The stronger pooled comparison allows a different setting for each task under one combined lookup ceiling. It resamples held-out questions within each task and reselects the highest-scoring affordable pair in each of 4,096 draws. The archive was used in the previous exact-nominee comparison. Here it tests a first-gain policy chosen on the math archive. [Runner](../benchmarks/certified_strict_gain_transfer.py) · [Sealed results](certified-strict-gain-transfer-v1.json)

## Results

Each cell shows held-out passes and paid lookups.

| Archive | Exact nominee | 18-read cap | 14-read cap |
| --- | ---: | ---: | ---: |
| GSM8K | 2,440 / 797 | 2,436 / 786 | 2,436 / 786 |
| SST-5 | 1,439 / 1,539 | 1,441 / 1,392 | 1,424 / 1,366 |
| Pooled | 3,879 / 2,336 | 3,877 / 2,178 | 3,860 / 2,152 |

The 18-read cap saved 158 lookups, or 6.8%, against exact nomination while scoring two fewer passes. The pooled paired 95% range was −0.24 to +0.17 percentage points. It changed two final prompts on GSM8K and six on SST-5. On SST-5 it changed three cycle schedules. The 14-read cap saved another 26 lookups and lost 17 more passes, all on SST-5.

Allowing controls to choose a different setting per task raised the strongest affordable native GEPA score from 3,565 to 3,646 passes at the 18-read variant's pooled budget. GEPA used 2,139 lookups, and CPO led by 231 passes with a paired range of +2.50 to +5.28 percentage points. The strongest overall control used halving with a cap of eight on both tasks, scoring 3,820 in 2,011 lookups. CPO led by 57 passes, with a paired range of +0.33 to +1.65 points.

Against halving at each task's own budget, the 18-read variant gained 45 passes on GSM8K (+0.56 to +2.50 points) and 38 on SST-5 (+0.21 to +2.40 points). The 14-read variant's SST-5 range included zero. These comparisons support the 18-read variant on this archive. The experiment used shared archived prompts and recorded grades. Fresh proposal performance and end-to-end model cost remain unverified.

The same policy is available through the opt-in episode API. [Usage and wheel verification](first-gain-episode.md)

## Reproduce offline

Use Python 3.12, the hash-pinned GEPA 0.1.4 wheel, and the original Promptolution archive. Run without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.certified_strict_gain_transfer \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute c7276c10ebb796cd01e834d117d9a927a359d4c329c913adf3073700805e3a29 \
  --out NEW_REPORT.json
```

Both complete runs blocked sockets and DNS and produced byte-identical results with SHA-256 `880b8d10670ddfb6e558d03fdf09075d27f5265bd0eb8933eb290ecf2971e335`. All 28 focused tests passed. They checked the pooled selector against exhaustive pair search and verified that the qualification audit follows the deployed incumbent. The CLI refused a stale seal, an existing output path, and an incorrect corpus. The replay sent zero provider requests. Storage Guard measured 8.8 GiB free, and the bounded workspace measured 125 MiB under the standing LAB exception. [Tests](../tests/unit/test_certified_strict_gain_transfer.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
