# Smaller challenger validation panels

Using 12 validation cases with a 52-lookup cap raised archive-enabled CPO from 10,236 to 10,265 transfer passes and reduced paid lookups from 81,269 to 53,054. It beat both original full-budget GEPA controls in aggregate and cleared both gates on three of eight panels. Against GEPA with the same 12-case panel, cap, and archive policy, CPO gained passes in aggregate and still spent more. No transfer panel cleared both matched gates. [Results and seals](prompteval-validation-size-results-v1.json)

## Protocol

Each smaller panel takes a prefix of the original seeded 24-case validation panel. Training cases, proposal order, the four separate eight-case qualification panels, and fixed final holdout stay the same. The qualification gate still requires a strict paired gain. All methods use the same panel size and search ceiling within each comparison. The scaled caps fund full incumbent validation, one batched GEPA round, and up to eight archived challenger lookups. Both original 171-lookup GEPA controls also remain in the comparison. [Role attribution and parent protocol](prompteval-round-reserve.md)

## Transfer results

Each cell reports final holdout passes and paid lookups with the same runner-up archive policy across eight recorded panels.

| Validation cases / search cap | CPO | Sequential GEPA | Batched GEPA |
| --- | ---: | ---: | ---: |
| 24 / 88 | 10,236 / 81,269 | 10,229 / 69,558 | 10,269 / 45,874 |
| 12 / 88 | 10,263 / 81,908 | 10,223 / 63,986 | 10,250 / 59,325 |
| 12 / 52 | 10,265 / 53,054 | 10,219 / 43,164 | 10,244 / 30,632 |
| 8 / 40 | 10,242 / 43,015 | 10,210 / 34,370 | 10,241 / 24,533 |

The 12-case scaled policy gained 29 passes and saved 28,215 lookups against 24-case CPO. It used 16,632 fewer lookups on complete challengers. At the unchanged cap of 88, a smaller panel let CPO cost more despite reading fewer rows per candidate. Cutting to eight cases saved a further 10,039 lookups and lost 23 passes relative to 12 cases at cap 52. The 12-case scaled policy also gained five passes and saved 13,770 lookups on the four development panels.

Both scaled policies still need fewer paid lookups to clear the matched GEPA gate. The PromptEval archive supplies all prompts, reuses final holdout cases across episodes, and provides no critical labels. This evidence supports smaller validation panels as a way to improve replay efficiency. It leaves fresh-model performance open.

The frozen 12-case policy transferred its own-cost savings to six other panels and still missed all matched GEPA gates. [Disjoint-subject replay](prompteval-validation-transfer.md)

## Reproduce offline

Use pinned GEPA 0.1.4. Preview each phase, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_validation_size \
  --phase retrospective-transfer
```

Two runs of each phase produced byte-identical reports. The full-panel controls reproduced the preceding pass and lookup totals by role. The report records per-panel summaries and full report and episode trace digests. [Runner](../benchmarks/prompteval_validation_size.py) · [Tests](../tests/test_prompteval_validation_size.py)
