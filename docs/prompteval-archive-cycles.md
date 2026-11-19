# Requalifying past contenders across optimization cycles

On the eight PromptEval transfer panels, rechecking past runners-up increased CPO from 10,270 to 10,305 final passes and cut paid lookups by 13.5% at the original search cap. It still spent 150,854 lookups against 84,758 for batched GEPA with the same archive policy. No transfer panel cleared both matched GEPA gates. [Results and seals](prompteval-archive-cycles-results-v1.json)

## Protocol

The benchmark preserves the existing four-cycle schedule. Each episode supplies the same starting prompt, four blocks of new prompts, and separate training, validation, qualification, and final holdout cases. Each arm keeps its own archive within the episode. The retired policy tries a previously displaced incumbent. The runner-up policy can also try a challenger that previously lost qualification. Both choose the most recent eligible prompt and attempt each directed incumbent–candidate pair once. [Source replay](prompteval-continuous.md)

Before search, an archived choice must prove a strict gain over the current incumbent on the current cycle's separate qualification cases. The certificate reads enough cases to fix the full-panel decision. A pass skips search. A failure deducts the archive's challenger lookups from the search budget and reuses the incumbent's qualification scores if search later nominates a challenger. The same policy and accounting apply to CPO and both official GEPA 0.1.4 controls. The benchmark enforces the original combined search and qualification ceiling for each configured cap.

## Transfer results

Each cell shows final holdout passes and total paid lookups across the eight transfer panels.

| Method | Search cap 171 | Search cap 88 | Search cap 76 |
| --- | ---: | ---: | ---: |
| CPO, standard | 10,270 / 174,349 | 10,210 / 88,643 | 10,238 / 75,550 |
| CPO, retired | 10,291 / 168,382 | 10,204 / 86,910 | 10,227 / 74,504 |
| CPO, runner-up | 10,305 / 150,854 | 10,236 / 81,269 | 10,230 / 70,155 |
| Sequential GEPA, runner-up | 10,227 / 88,819 | 10,229 / 69,558 | 10,229 / 58,545 |
| Batched GEPA, runner-up | 10,266 / 84,758 | 10,269 / 45,874 | 10,224 / 24,576 |

The runner-up policy bypassed 160 of 1,024 CPO searches at the original cap and 118 at cap 88. On the four development panels it preserved the original 4,192 total passes and saved 9,462 lookups at cap 171. The replay added cap 88 after observing that cap 76 left the original batched GEPA adapter with no affordable proposal round. Cap 88 permits one batched round after 24 incumbent validation lookups and up to eight extra archive lookups.

At cap 88, runner-up CPO gained 26 passes and saved 7,374 lookups against standard CPO. It cleared the gate against both published full-budget GEPA controls on two transfer panels, compared with zero for standard CPO at 88. It cleared no transfer panel against both same-cap GEPA controls. The published standard controls at cap 171 scored 10,236 and 10,263 passes for 91,649 and 88,226 calls. Those comparisons preserve a fully funded reference for the smaller caps. Search still acts on supplied prompts and repeated archived cases. Fresh provider behavior remains unmeasured.

## Reproduce offline

Use the pinned GEPA 0.1.4 benchmark dependency. Preview each plan, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. The archived development and transfer phases have separate seals for each cap.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_archive_cycles \
  --phase retrospective-transfer --search-cap 88
```

Two runs of each configuration produced identical reports. The cap-171 controls reproduced the previously published panel totals. The result file records full report hashes and episode trace digests, panel costs, and gate outcomes. [Runner](../benchmarks/prompteval_archive_cycles.py) · [Tests](../tests/test_prompteval_archive_cycles.py)
