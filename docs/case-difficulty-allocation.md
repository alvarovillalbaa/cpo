# Estimate case difficulty from paid validation replies

Posterior allocation improved selection on archived ARC-AGI, but its MMLU transfers missed the combined accuracy and lookup gate. The allocator assigned a prompt's unread cases one pass probability distribution even after observing other prompts on those cases. This replay tests whether accounting for that case-level evidence improves allocation in the wider branch of the original CPO route. [Recorded mathematics replay](recorded-score-allocation.md) · [Most recent transfer](posterior-model-transfer.md)

For each case, the new forecast starts with smoothed pass odds from the incumbent and other observed prompts on that case. It excludes the contender's own reply when estimating case difficulty. The contender's measured replies update five equally weighted ability multipliers on those odds. For each multiplier, the forecast computes the probability of reaching the required pass count and passing every outstanding protected case. The combined probability ranks contenders. The next-case order, paid search cap, exact nomination, deterministic ties, and disjoint qualification follow the original posterior allocator. [Runner](../benchmarks/case_difficulty_allocation.py)

The replay uses the existing 16 Llama and Mistral panels and 12 Gemma and Flan panels, with the original four-cycle schedules. The gate on each cohort requires at least 10% lookup savings against both official cap-52 GEPA arms and a nonnegative lower endpoint of the joint 95% paired case range. The cap-47 batched GEPA, exact-wide, original route, original posterior-wide, and retain-start controls provide context. These are retrospective checks on existing outcomes.

## Results

Each cell gives holdout passes and total paid search and qualification lookups.

| Method | Llama and Mistral | Gemma and Flan |
| --- | ---: | ---: |
| Retain start | 17,617 / 0 | 17,404 / 0 |
| Original route | 17,724 / 49,330 | 17,435 / 35,496 |
| Exact-wide | 17,710 / 50,898 | 17,438 / 36,527 |
| Posterior-wide | 17,727 / 51,141 | 17,434 / 36,665 |
| Case-specific forecast | 17,729 / 51,045 | 17,438 / 36,676 |
| Batched GEPA, cap 47 | 17,687 / 45,679 | 17,407 / 31,608 |
| Batched GEPA, cap 52 | 17,694 / 57,271 | 17,422 / 40,184 |
| Sequential GEPA, cap 52 | 17,721 / 81,537 | 17,409 / 60,951 |

The new forecast gained two passes and saved 96 lookups against the original posterior allocator on Llama and Mistral. Its paired range against that allocator was −5 to +9 passes. It saved 10.9% against batched GEPA at cap 52 and 37.4% against sequential GEPA at cap 52. The joint paired range was −53 to +63, leaving the gate inconclusive.

On Gemma and Flan the forecast gained four passes and used 11 more lookups than the original posterior allocator. It tied exact-wide and used 149 more lookups. Its 8.7% savings against batched GEPA at cap 52 missed the threshold, and its joint paired range was −34 to +63. The experiment leaves the existing selector in place. [Per-panel results, costs, and paired ranges](case-difficulty-allocation-results-v1.json)

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two replays in source exports matched byte for byte with sockets and DNS blocked. They matched 196 published panel-control records. An exhaustive check over 28,672 binary matrix, critical-case, and budget combinations verified cap enforcement, exact scoring, critical preservation, and exhaustive ranking at full funding. The CLI rejected a wrong seal and preserved an existing report. Storage Guard measured 12.3 GiB free. The 19.5 MB scratch overlay was removed under the standing LAB exception. [Verification receipt](case-difficulty-allocation-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.case_difficulty_allocation \
  --execute f603258972431049683afcf65c9bb482c9e56c9a946429604667a18b475c2127 \
  --out NEW_REPORT.json
```
