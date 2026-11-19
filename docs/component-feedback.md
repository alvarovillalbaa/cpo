# Reusing measured training feedback across component edits

The earlier merge study repaired some proposals after observing training regressions. This benchmark uses those diagnostics during ordinary proposal generation. It compares a rotating editor, an always-guarded editor, an editor using paid training observations on the current parent, and an editor that also reuses compatible observations from previously evaluated programs. [Training-counterexample merge repair](component-merge-repair.md)

The feedback editors prioritize diagnosed conflicts and regressions before missing behavior. The archive reuses a component's local diagnostic only while that component has the same value. Each affected training case votes once per action. Interaction diagnostics stay with the exact parent that produced them. Search and holdout cases remain disjoint. A deterministic fixture defines the diagnoses and permissible edits, so the experiment tests this feedback rule under a known component model.

The suite uses 16 fresh seeds on four fixture profiles. It runs each arm with two or six training observations per reflection and search caps of 96 and 144. The official GEPA arms use the same scripted editors and caps. One enables native merging with archive feedback. Costs include distinct evaluations and scripted reflection slots.

## Six training observations and cap 96

| Method | Held-out passes | Charged calls |
| --- | ---: | ---: |
| CPO, rotating edits | 1,799 | 5,752 |
| CPO, always-guarded edits | 2,134 | 5,350 |
| CPO, current-parent feedback | 2,131 | 5,231 |
| CPO, compatible feedback archive | 2,152 | 5,186 |
| GEPA, always-guarded edits | 1,697 | 5,827 |
| GEPA, current-parent feedback | 1,485 | 5,954 |
| GEPA, compatible feedback archive | 1,482 | 5,936 |
| GEPA, archive and native merge | 1,511 | 5,947 |

CPO with archived feedback cleared all four GEPA controls on all four fixture profiles at this setting. It preserved every matched critical pass. Compared with CPO using only current-parent feedback, it gained 21 passes and saved 45 calls. Compared with always-guarded CPO, it gained 18 passes and saved 164 calls overall. It still lost 17 passes on the multi-clause profile against that control.

With six observations and cap 144, the archive cleared the three feedback-based GEPA controls on all four profiles and the always-guarded GEPA control on three. With two observations, it cleared all four GEPA controls only on legacy-heavy and reverse-precedence at cap 96 and on zero profiles at cap 144. The archive policy remains experimental. These fixtures use explicit diagnostics whose component scope is known. Transfer to live model feedback remains open. [Full results and seal](component-feedback-results-v1.json)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
PYTHONHASHSEED=0 python -m benchmarks.component_feedback
PYTHONHASHSEED=0 python -m benchmarks.component_feedback --execute PLAN_SHA256 --out result.json
```

The report records exact holdout outcomes, matched critical comparisons, search costs, and the ordered search digest. [Runner](../benchmarks/component_feedback.py) · [Scope and deduplication tests](../tests/test_component_feedback.py)
