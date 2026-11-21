# Compare certificate policies at matched GEPA lookup budgets

The frozen four-read certificate policy used fewer lookups and scored below GEPA at the original search cap on disjoint LMentry and BBH tasks. This follow-up asks whether GEPA can reach those scores at the same realized cost. It retains the archived CPO deployments, paid costs, and held-out grades. It replays sequential and batched GEPA 0.1.4 at every integer search cap from 6 through 180 on the same prompt rosters, seeds, and case splits, with the same expected-cost qualification. Costs count paid search and qualification lookups. [Frozen transfer](recorded-certificate-allowance-transfer.md) · [Frontier runner](../benchmarks/recorded_certificate_cost_frontier.py)

Each affordable GEPA setting uses one mode and cap across the whole cohort. The comparator can also retain every start at zero cost. The 4,096 paired draws resample cases within a task and keep both models and all seeds together. Each draw reselects the strongest setting within the frozen CPO policy's realized budget. The replay compresses adjacent integer caps when they permit the same sequence of reserved GEPA rounds. Every panel and both modes reproduced the original-cap paid counts and path hashes. [Full costs and resampled choices](recorded-certificate-cost-frontier-results-v1.json)

| Target tasks | CPO policy | CPO passes / lookups | Best affordable GEPA passes / lookups | Pass difference | Paired 95% range |
| --- | --- | ---: | ---: | ---: | ---: |
| Disjoint LMentry | Four reads | 4,924 / 11,045 | 5,046 / 10,710 | −122 | −178 to −67 |
| Disjoint LMentry | First certificate | 4,790 / 10,459 | 4,964 / 9,741 | −174 | −230 to −121 |
| Disjoint BBH | Four reads | 6,544 / 20,468 | 6,598 / 20,018 | −54 | −125 to +14 |
| Disjoint BBH | First certificate | 6,485 / 19,655 | 6,555 / 18,634 | −70 | −143 to −7 |
| Original LMentry on different models | Four reads | 699 / 4,568 | 660 / 4,533 | +39 | +16 to +62 |
| Original LMentry on different models | First certificate | 699 / 4,308 | 642 / 4,082 | +57 | +33 to +80 |
| Original BBH on different models | Four reads | 3,046 / 7,963 | 3,072 / 7,877 | −26 | −59 to −2 |
| Original BBH on different models | First certificate | 3,022 / 7,690 | 3,062 / 7,637 | −40 | −71 to −13 |

On six disjoint LMentry tasks, sequential GEPA at cap 28 exceeded the four-read score by 13 passes while using 1,710 fewer lookups. Batched GEPA at cap 40 similarly exceeded the four-read score on disjoint BBH by 11 passes while using 1,834 fewer lookups. The fixed-cap lookup savings did not establish a point on the matched-cost frontier in either cohort.

On the original homophones and word-before tasks with different model checkpoints, no swept GEPA setting reached 699 passes at any cost. The first-certificate policy retained those 699 passes while spending 260 fewer lookups than the four-read policy. This advantage is specific to the two archived tasks. Broader task transfer and fresh prompt generation remain unverified.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and socket connections blocked, 45 targeted tests passed and two full replays matched byte for byte. The boundary tests checked every integer cap on a fixed nine-prompt pool for both GEPA modes. Direct replay reproduced the 13 reported best-affordable and least-cost matching GEPA settings over 4,736 archived trials. The CLI rejected a stale seal, and the ordered live plan preview matched. Storage Guard measured 4.8 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The sweeps sent zero provider requests. [Round boundary tests](../tests/unit/test_recorded_certificate_cost_frontier.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_certificate_cost_frontier
python -B -m benchmarks.recorded_certificate_cost_frontier \
  --execute 92d90c117e275533940720734c90f81cb5793f64205635cfa758cbf2c583ec8e \
  --out NEW_REPORT.json
```
