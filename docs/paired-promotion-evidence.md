# Use paired wins and losses to decide promotion

An extra validation certificate only helps if the promoted prompt holds up on new cases. After paid incumbent credit increased certificates and reduced final accuracy at cap 28, this replay kept the seeded search and changed what counts as a qualification gain. A paired win means only the challenger passed the case. A paired loss means only the incumbent passed. A candidate with two wins and zero losses and one with three wins and one loss have the same net gain. The stricter paired gate accepts the first and rejects the second. [Paid incumbent credit](paid-incumbent-credit.md) · [Benchmark runner](../benchmarks/paired_promotion_evidence.py)

| Policy | Qualification requirement |
| --- | --- |
| Seeded | At least one net gain |
| Fixed two-pass | At least two net gains |
| Paired evidence | A one-sided exact sign-test tail of at most 1/4 over discordant pairs |
| Paired win ratio | At least one win and at least twice as many wins as losses |

The sign-test cutoff is a search heuristic. Each gate applies to fresh challengers and archive retries. The paired gates stop reading once the remaining outcomes cannot reverse the decision. They retain the seeded read order for fresh challengers and the incumbent-first order for archive retries. The replay uses a single case family and one repeat per pair. The gate also protects incumbent critical passes, which the contract test exercises. The recorded matrices supply binary correctness without critical labels. Every policy keeps the original proposal rosters, search ceiling of 52, episode-local cache, and independent qualification panels of eight cases. The final holdout scores each chosen prompt after search has finished. [Earlier qualification margins](starting-prompt-margin.md) · [Paired qualification contract](paired-qualification.md)

## Results

Each cell is final holdout passes and paid lookups. Both GEPA modes in the source reports provide the panel-level controls. On Flan-UL2 and Mixtral they use the fixed replication settings at sequential cap 31 and batched cap 44. The other cohorts use the original paid-cap 52 controls. [Replication controls](low-budget-transfer.md) · [GEPA paid-cap controls](gepa-paid-cap-transfer.md)

| Cohort | Seeded | Fixed two-pass | Paired evidence | Paired win ratio | Batched GEPA |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gemma and Falcon MMLU | 8,971 / 21,477 | 8,951 / 21,514 | 8,950 / 21,411 | 8,968 / 21,463 | 8,996 / 29,285 |
| Flan-UL2 and Mixtral MMLU | 18,842 / 31,705 | 18,865 / 31,358 | 18,862 / 31,213 | 18,842 / 31,678 | 18,866 / 30,649 |
| Earlier MMLU | 7,743 / 22,531 | 7,705 / 22,430 | 7,705 / 22,309 | 7,743 / 22,522 | 7,729 / 27,767 |
| BBH and LMentry | 6,380 / 40,406 | 6,393 / 41,023 | 6,387 / 40,611 | 6,378 / 40,530 | 6,341 / 48,743 |
| BBH and LMentry stress | 6,900 / 38,097 | 6,942 / 38,759 | 6,919 / 38,426 | 6,908 / 38,149 | 6,676 / 46,627 |

The paired-evidence gate cut promotions from 1,090 to 475. It gained 20 passes and saved 492 lookups against seeded CPO on Flan-UL2 and Mixtral. There, batched GEPA still scored four more passes and used 564 fewer lookups. Across all five cohorts the gate scored 13 fewer passes and used 246 fewer lookups than seeded CPO. It saved 1,114 lookups and lost 33 passes against the fixed two-pass gate.

The win-ratio gate kept 1,052 promotions. It added three passes and used 126 additional lookups across the five cohorts. Seeded and win ratio cleared both GEPA cost-and-accuracy gates on 18 of 52 panels, fixed two-pass on 17, and paired evidence on 16. The five cohorts were available before this replay. The results leave the seeded gate as the default. [Sealed per-panel results](paired-promotion-evidence-results-v1.json)

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Preview each phase to get its seal. Other phases are `independent`, `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.paired_promotion_evidence --phase replication
PYTHONHASHSEED=0 python -B -m benchmarks.paired_promotion_evidence \
  --phase replication --execute fea4210c824f75045522e95ca1a38d2cbf8c303bd234822193853c1956affa2e \
  --out NEW_REPORT.json
```

Two executions per phase agreed byte for byte with DNS and outbound sockets blocked. The replay reproduced all 52 seeded panel traces and rejected a stale seal. The exhaustive contract test checked all completions after the early decision for 1,536 combinations of panel outcomes, gates, and read orders. Storage Guard measured 13.6 GiB free. The standing LAB exception covered the 9.7 MB reproducible scratch overlay, which was removed. Fresh prompt generation and provider costs remain unverified. [Contract test](../tests/unit/test_paired_promotion_evidence.py)
