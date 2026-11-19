# Where CPO spends its search budget

At the 88-lookup search cap, CPO spent 35,269 more validation lookups than batched GEPA with the same archive policy. Of that gap, 30,744 came from scoring challengers on all 24 validation cases. The GEPA adapter completed no challenger validation panels in this replay. The difference in training probes favors CPO, so it offsets part of the validation gap. [Role counts and seals](prompteval-round-reserve-results-v1.json)

## Measurement

The replay uses the same PromptEval schedules and archived runner-up policies as the preceding benchmark. It counts distinct paid lookups for training, validation, and qualification. Validation lookups are grouped by incumbent, challengers observed on all 24 assigned cases, and challengers observed on a subset. The categories describe observations, including the work needed to eliminate some partial challengers. [Parent replay](prompteval-archive-cycles.md)

The comparison tests the library's existing fixed-round mode. It uses `adaptive=False`, which also keeps the supplied proposal branch order. The experiment therefore measures the existing mode as a whole. Both official GEPA 0.1.4 controls use their original policies and keep identical totals under either CPO setting. PromptEval supplies binary correctness and has no critical case labels in this replay.

## Transfer results

All rows below use the same runner-up policy across the eight transfer panels.

| Search cap and method | Final passes | Training | Validation | Qualification | Total lookups |
| --- | ---: | ---: | ---: | ---: | ---: |
| 88, adaptive CPO | 10,236 | 1,047 | 65,221 | 15,001 | 81,269 |
| 88, fixed-round CPO | 10,247 | 1,997 | 64,500 | 14,271 | 80,768 |
| 88, batched GEPA | 10,269 | 12,484 | 29,952 | 3,438 | 45,874 |
| 171, adaptive CPO | 10,305 | 5,339 | 127,847 | 17,668 | 150,854 |
| 171, fixed-round CPO | 10,243 | 7,563 | 124,265 | 17,301 | 149,129 |
| 171, batched GEPA | 10,266 | 35,496 | 41,686 | 7,576 | 84,758 |

At cap 88, fixed-round CPO gained 11 passes and saved 501 lookups. It scored 43 fewer complete challenger panels, spent 1,032 fewer lookups on those panels, and redirected some of the savings into training and partial validation. At cap 171, the fixed-round policy saved 1,725 lookups and lost 62 passes. Across both caps and both evaluation cohorts, no CPO setting cleared both matched GEPA gates on a panel. Substantially reducing the cost gap requires changing when CPO funds full challenger validation. The measured evidence covers supplied proposals and repeated recorded cases.

The follow-up reduced challenger validation to 12 or eight cases while preserving the separate qualification gate. [Validation size comparison](prompteval-validation-size.md)

## Reproduce offline

Use pinned GEPA 0.1.4. Preview the configuration, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. Each development and transfer configuration has a separate seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_round_reserve \
  --phase retrospective-transfer --cap 88
```

Two runs of every configuration returned identical reports. Each adaptive arm reproduced the corresponding published aggregate and reconciled every lookup to its role. [Runner](../benchmarks/prompteval_round_reserve.py) · [Tests](../tests/test_prompteval_round_reserve.py)
