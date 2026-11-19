# Independent holdout evidence for the archive replay

The 220-holdout promotion replay reused 12 recorded development cases per task. This audit checked the selected CPO and GEPA prompts against the source study’s separate, 18-case provider holdout. Repeated selection of the same prompts across replay splits counts as one physical prompt pair. [Promotion-coverage replay](recorded-promotion-coverage.md)

## Verified evidence

The audit matched all 288 distinct holdout provider receipts to their archived observations across ticket, warehouse, and outage. It rescored the raw output with the original structured grader and checked prompt fingerprints. It also verified that each source holdout was recorded after search and that its task inputs did not overlap training or validation after the record-ID prefix was removed. Duplicate grades for a prompt and case agreed.

| Task | Provider holdout replies verified | Distinct prompt-case outcomes | Distinct CPO–GEPA prompt pairs | Pairs with complete original holdout |
| --- | ---: | ---: | ---: | ---: |
| Ticket | 108 | 54 | 0 | 0 |
| Warehouse | 90 | 54 | 0 | 0 |
| Outage | 90 | 54 | 5 | 1 |

Ticket and warehouse selected identical prompts across the audited arms. Outage had eight directed comparisons among five distinct prompt pairs. The one fully observed pair appeared in both directions. CPO selected the 18-pass prompt versus GEPA’s nine-pass prompt in 76 replay comparisons. It selected the nine-pass prompt versus GEPA’s 18-pass prompt in two. In that latter direction, the original provider holdout showed four matched critical losses. The 76 and two are selection counts. Both directions use the same archived provider evidence.

The other four pairs depend on two selected prompts with no scored replies on the original holdout. The audit found and verified both exact archived prompt texts. Completing the historical matrix would require 36 missing prompt-case outcomes. The recorded results establish an external critical regression for one of the three distinct outage directions that lost critical passes in replay. The other two lack paired external evidence. The available results leave CPO’s independent outage superiority unverified. [Sealed audit totals](recorded-independent-holdout-results-v1.json)

## Reproduce

Use the prior promotion replay’s full output, the GEPA research archive, and the Open Evals checkout containing its source grader. The audit verifies the published replay fingerprint before reading the provider archive.

```sh
PYTHONPATH=/path/to/gepa-research python -m benchmarks.recorded_independent_holdout \
  --replay FULL_PROMOTION_REPLAY.json
PYTHONPATH=/path/to/gepa-research python -m benchmarks.recorded_independent_holdout \
  --replay FULL_PROMOTION_REPLAY.json --execute PLAN_SHA256 --out result.json
```

The public results contain aggregate evidence. Raw replies and the prompt-by-case gap list remain in the research archive. The audit sends no provider requests.
