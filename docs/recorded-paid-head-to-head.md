# Rerank strict validation certificates on shared paid cases

The nominee audit found some useful alternatives already certified when CPO finished full validation. This replay chooses among those certificates using only the validation replies that the original race bought. Each alternative still has to prove a strict gain over the incumbent and preserve all protected validation passes. Search makes one independent qualification attempt on the selected nominee. This is the original policy without a training check. [Paid nominee evidence](recorded-bounded-certificate-backup.md) · [Replay runner](../benchmarks/recorded_paid_head_to_head.py)

The alternative must win at least one case the original nominee lost and have at least as many wins as losses on the exact same paid cases. The second version also requires that it retain every incumbent pass on cases already read for that alternative. The original roster breaks ranking ties after net gain, fewer losses, certified passes, and number of shared cases.

Strict positive head-to-head evidence cannot survive this validation race. On the paid subset, the score difference is the original winner's misses minus the alternative's misses. The upper-bound cutoff requires at least as many paid misses as the eventual winner had across the full panel. Fully observed alternatives also cannot outscore the selected winner. The independent audit confirmed this bound on all original trials. The tested changes therefore use evidence ties between prompts with different repairs.

| Archive and roster | Original passes / lookups | Use paid head-to-head tie | Also preserve observed incumbent passes |
| --- | ---: | ---: | ---: |
| AIME, original, four challengers | 486 / 1,040 | 491 / 1,040 | 491 / 1,040 |
| AIME, original, eight challengers | 476 / 1,438 | 479 / 1,438 | 479 / 1,439 |
| AIME, rotated, four challengers | 4,036 / 7,643 | 4,040 / 7,644 | 4,041 / 7,640 |
| AIME, rotated, eight challengers | 4,002 / 10,908 | 4,007 / 10,906 | 4,007 / 10,905 |
| ARC-AGI, original, four challengers | 1,561 / 1,302 | 1,560 / 1,303 | 1,556 / 1,303 |
| ARC-AGI, original, eight challengers | 1,578 / 1,502 | 1,547 / 1,501 | 1,547 / 1,501 |
| ARC-AGI, rotated, four challengers | 13,878 / 7,007 | 13,876 / 7,005 | 13,878 / 7,007 |
| ARC-AGI, rotated, eight challengers | 13,932 / 8,239 | 13,931 / 8,236 | 13,932 / 8,239 |

On eight-challenger rotated AIME, requiring incumbent-pass preservation changed 13 nominations and two deployments. It gained five passes and saved three lookups, all from the independent proof. It still trailed affordable GEPA by 73 passes with a paired 95% range of −133 to −38. The tie rule lost 31 passes on the original eight-challenger ARC-AGI start. On its rotation it changed two deployments and lost one pass. The incumbent-preserving rule reproduced the original ARC-AGI rotation exactly. [Sealed results and matched costs](recorded-paid-head-to-head-results-v1.json)

The hindsight diagnostic can keep the original result or choose any admitted alternative after seeing its independent qualification and final holdout. A rejected alternative deploys the incumbent. On the eight-challenger rotations, the tie rule's offer set could add at most seven AIME passes and three ARC-AGI passes. The incumbent-preserving version could add seven and zero respectively. The offer sets cover little of the earlier roster headroom, and the rules stay out of the default policy.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two socket- and DNS-blocked replays matched byte for byte. The original search-and-proof traces and native GEPA frontiers reproduced. All 59 targeted tests passed from a clean source export, including paid-only selection and protected passes. An independent check verified all 3,040 decisions using the original paid validation ledger and complete independent grades. The CLI rejected the earlier seal. The public selector receipt and ordered live-plan preview reproduced. Storage Guard measured 2.8 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_paid_head_to_head
python -B -m benchmarks.recorded_paid_head_to_head \
  --execute 9871a61c610e63ff97d5d36b893660076fcb71b400f03a6c75a2b2f9d6bb4022 \
  --out NEW_REPORT.json
```
