# Transfer the language-archive router to AIME and ARC-AGI

The language-archive experiments found modest gains from joint qualification ordering and task-balanced terminal backups. This replay moves that frozen policy to two separate archives. AIME has nine scored candidates and 45 problems. ARC-AGI has ten scored candidates and 80 problems. Both were used in earlier CPO studies. Their task names are absent from the language router's discovery enrollment. [Reduced archive and provenance](../benchmarks/data/gepa-recorded-math-v1.json) · [Earlier fixed-pool study](recorded-math-validation-ties.md) · [Transfer runner](../benchmarks/recorded_math_router_transfer.py)

The replay keeps the original 40 seeds per archive, root and rotated incumbents, four and eight challengers, and the original training, validation, qualification and holdout splits. Each episode is one cycle. The recorded pools have too few distinct prompts to re-create the three-cycle eight-challenger layout. The transferred router keeps its 19-read search cap and the original fallback for unseen routing states. On ARC-AGI the full six-case qualification panel uses weights estimated from the language archives. No weights are refitted.

The study compares the frozen router with its original and joint-order proofs. It verifies that the change in order preserves every nomination and deployment. For each root or rotation setting, any aggregate lookup savings across the two archives fund a pooled task-balanced terminal backup arm. That arm uses the original one-probe queue after a proved rejection and can spend up to the measured savings. The strict math CPO arm reproduces the previously published score and lookup count at its original cap of 180.

The two native GEPA modes use disjoint training and validation cache identities. They sweep every funded integer search cap through 180, at full and half validation width and with all six proof wrappers from the language comparison. The strongest affordable native setting is selected separately for each archive and CPO policy, then replayed to verify its price and held-out grades. Uniform scoring and successive halving sweep their funded round prefixes with the same joint qualification rule as CPO. The match includes search and qualification lookups and the zero-cost option of keeping the incumbent. It uses lookup units. The original ARC historical evaluator prices are a separate accounting basis.

A capacity diagnostic lets terminal backups use the larger historical strict-math CPO budget, in lookup units. It retains the frozen joint-proof primary cycles and uses the same full quotes. For each archive it also computes a hindsight upper bound with the entire pooled backup allowance available to that archive. The bound uses actual settled charges and relaxes quote timing. This diagnostic compares backup capacity and the earlier strict score at a wider ceiling. [Capacity runner](../benchmarks/recorded_math_backup_capacity.py)

## Transfer results

Cells show held-out passes and paid lookups. The two matched columns use the joint-proof router's spend. The strict math CPO column gives its originally published, higher-price result.

| Archive and setting | Joint-proof router | Best affordable GEPA or retention | Best affordable simple control | Strict math CPO |
| --- | ---: | ---: | ---: | ---: |
| AIME, root, four | 495 / 413 | 500 / 0 | 501 / 317 | 486 / 1,016 |
| AIME, root, eight | 489 / 489 | 500 / 0 | 501 / 317 | 476 / 1,422 |
| AIME, rotated, four | 4,056 / 3,222 | 4,067 / 2,857 | 4,056 / 0 | 4,036 / 7,726 |
| AIME, rotated, eight | 4,052 / 3,951 | 4,067 / 2,857 | 4,056 / 0 | 4,002 / 11,166 |
| ARC-AGI, root, four | 1,358 / 586 | 575 / 0 | 1,132 / 434 | 1,561 / 1,308 |
| ARC-AGI, root, eight | 1,358 / 640 | 575 / 0 | 1,334 / 612 | 1,578 / 1,507 |
| ARC-AGI, rotated, four | 13,563 / 3,207 | 13,315 / 2,894 | 13,274 / 2,840 | 13,878 / 8,636 |
| ARC-AGI, rotated, eight | 13,591 / 3,534 | 13,486 / 3,445 | 13,274 / 2,840 | 13,932 / 10,383 |

The transferred router beat both affordable control menus on all four ARC-AGI settings. On the eight-challenger rotation, its paired 95% ranges were +62 to +147 versus split-safe GEPA and +235 to +399 versus the simple control. It scored below the strongest affordable GEPA or retention point in all four AIME settings. The two root runs chose retention as the most affordable high-score native alternative. All AIME ranges against the selected GEPA control crossed zero.

Joint ordering preserved every nomination and deployment across 1,520 episodes. It added 33 lookups over the original order, and each combined archive setting was more expensive. There was no saved budget for terminal backups in the primary comparison.

[Root, four](recorded-math-router-transfer-root-4-v1.json) · [Root, eight](recorded-math-router-transfer-root-8-v1.json) · [Rotated, four](recorded-math-router-transfer-rotated-4-v1.json) · [Rotated, eight](recorded-math-router-transfer-rotated-8-v1.json)

## Backup capacity at the strict budget

On the ARC-AGI rotations, terminal backups gained 19 passes at both roster widths, spending 101 additional lookups with four challengers and 114 with eight. Hindsight could gain at most 29 and 71 passes, respectively. Those bounds leave gaps of at least 286 and 270 passes to strict math CPO. The root ARC-AGI starts had no eligible positive-gain backup even at the larger budget. On AIME the actual backup rule lost passes in all four settings, including eight passes on the eight-challenger rotation. [Capacity receipt](recorded-math-backup-capacity-v1.json)

The larger budget leaves a quality gap that the existing terminal backup menu cannot close on these recorded paths. The results measure archived prompt selection with reused problems. Fresh proposals, live transfer, and historical price dominance remain unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a plan's seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_math_router_transfer \
  --group rotated --width 8 \
  --execute f47c630393a80218a8bf51e840c721cfaf5f5d90bd929625210c51af93e982bf \
  --out NEW_REPORT.json
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_math_backup_capacity \
  --execute 87942181e19c37f9cb5c181cf02ef05e66a6dbbfe685edcaf7e01c9d63b7ef68 \
  --out NEW_CAPACITY.json
```

Nineteen targeted tests passed. Two CLI replays per setting and two capacity runs matched byte for byte with DNS and outbound sockets blocked. The strict math results and each selected GEPA setting reproduced their lookup counts and held-out scores. Storage Guard measured 9.9 GiB free. The export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_recorded_math_router_transfer.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
