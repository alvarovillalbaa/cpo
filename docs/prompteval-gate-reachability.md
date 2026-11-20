# Which scores can CPO reach under its promotion gates?

The first-gain screen finished below at least one matched GEPA control on several recorded panels. This audit asks how many of the losing episodes could reach a matching score through a different sequence of prompts. It replays the existing first-gain and GEPA arms, then uses the archived correctness matrix to enumerate the possible incumbent prompts after each cycle. [Measured arms](prompteval-paid-witness.md) · [Audit runner](../benchmarks/prompteval_gate_reachability.py)

Within each episode the available choices start with the recorded incumbent. Each subsequent cycle can keep its incumbent or take an eligible prompt from that cycle. The audit evaluates progressively wider sets of paths.

| Path | Eligibility for a fresh prompt |
| --- | --- |
| Strict, fresh only | Strict validation gain and strict paired qualification gain |
| Strict, with archive | Same fresh gate, with an optional archive move on a qualification gain |
| Allow validation ties | Match or improve validation and earn a strict qualification gain |
| Qualification only | Earn a strict qualification gain |
| Any offered prompt | Belong to the supplied proposal stream |

Archive-enabled bounds allow any previously offered prompt to qualify in a later cycle. This is deliberately more permissive than the replay's archive nomination rule. The auditor also lets a path keep the incumbent when an eligible archive move exists. The archived PromptEval rows carry no critical labels.

Each phase keeps the measured arms' original schedule, holdout, and evaluation budgets. The bounds skip lookup costs and choose the highest final holdout score among the reachable prompts. The holdout only scores the completed sets. These bounds measure the maximum opportunity available in the recorded matrix. They cannot estimate how reliably an optimizer could find a path at the original cost. Each loss is counted separately against sequential and batched GEPA.

## Results

Across 18 panels and 576 episodes, first-gain finished below sequential GEPA in 86 comparisons and below batched GEPA in 80. The table assigns each loss to the first bound that reached at least the GEPA score.

| First bound to match the control | Sequential GEPA | Batched GEPA |
| --- | ---: | ---: |
| Strict, fresh only | 78 | 75 |
| Strict, with optimistic archive | 7 | 4 |
| Allow validation ties | 1 | 1 |
| Qualification only | 0 | 0 |
| Any offered prompt | 0 | 0 |
| Total losing comparisons | 86 | 80 |

The strict fresh-only routes reached the comparison score in **153 of 166 losses**. The optimistic archive added 11, and allowing validation ties added two. Removing the validation gate altogether added none. This makes finding better paths through the existing gates a higher-priority hypothesis than relaxing the gates. It leaves the lookup cost and generalization of those paths unmeasured.

The measured first-gain replay scored 18,791 holdout passes at 66,481 paid lookups. The strict fresh-only ceiling was 19,698 passes, and the strict ceiling with archive was 20,487. These ceilings choose the highest holdout score after enumerating complete paths and reuse held-out cases across seeds. They describe available headroom on these panels. Two offline executions of each phase produced byte-identical reports. [Panel results and seals](prompteval-gate-reachability-results-v1.json)

A follow-up spread first probes across missed cases. This gained 54 aggregate holdout passes at a cost of 7,588 additional lookups under the existing gates. [Coverage rotation replay](prompteval-coverage-rotation.md)

The later MMLU audit counted which paths remain reachable at CPO’s observed episode cost and distinguished retaining the start from paying for fresh moves. [Priced reachability](priced-gate-reachability.md)

## Reproduce

Use pinned GEPA 0.1.4. Preview the phase, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_gate_reachability --phase finalist-transfer
```

The other phases are `development` and `retrospective-transfer`.
