# Conditional edits for conflicting component behavior

The earlier coverage study still found critical losses on risk types already represented in validation. This experiment tested a more expressive edit that can fix a witnessed interaction while retaining the old component value on other inputs. [Coverage study](component-risk-coverage.md)

## Protocol

The fixture provides a binary input label for single-rule and multi-rule cases. The global operator replaces one component value. The conditional operator starts with the same dependency-aware proposal. When every compatible training witness for a broadening is a multi-rule case, it edits only that branch. When compatible single-rule witnesses instead call for a guard, it can add the guard and retain the existing broad multi-rule behavior. Each proposal consumes one slot. A unit case demonstrates that the conditional repair fixes the interaction and preserves the legacy pass where global broadening regresses.

CPO and official GEPA 0.1.4 used each operator on the same training, validation, and held-out rows. GEPA ran with and without native merge. The benchmark used 32 fresh seeds, four deterministic profiles, caps of 96 and 144 evaluations, and two 12-row validation designs. Both designs used the same holdout. The six-critical design strata cover the risk groups defined by the preceding coverage study. The routing profiles share inputs and vary the available dependency declarations.

The transfer check re-scored each selected prompt after flipping the explicit condition label on seven of its 36 holdout inputs. Labels used during search stayed correct by construction. The grader kept the original task requirements. All unscoped programs produced identical results before and after the label shift.

## Results

Each row aggregates 9,216 deterministic held-out outcomes for CPO. Critical losses are relative to ordinary global-edit GEPA without merge on the same validation design. The conditional arm’s call count is the same in the clean and shifted columns because the shift happens after search.

| Validation | CPO operator | Exact passes, clean | Exact passes, shifted | Search calls | Critical losses, clean | Critical losses, shifted |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Original | Global | 6,359 | 6,359 | 25,473 | 545 | 545 |
| Original | Conditional | 6,461 | 6,451 | 25,615 | 429 | 451 |
| Six critical | Global | 6,701 | 6,701 | 25,842 | 78 | 78 |
| Six critical | Conditional | 6,642 | 6,614 | 25,822 | 78 | 116 |

Conditional edits added 102 exact passes and reduced critical losses by 116 on the original panels. They lost 59 exact passes and tied the critical loss count on the six-critical panels. On the six-critical routing panels, CPO still missed critical cases passed by GEPA when both used the same conditional operator. Approval had zero such losses on those panels and fewer exact passes than either conditional GEPA control. Native merge hit the previously recorded all-zero ancestor weights error for local seed `67543` in both original-panel configurations at both caps. Affected pairings omitted that seed and could not qualify.

An exhaustive check after selection allowed any of the 27 programs in each input branch while preserving the global GEPA winner’s critical passes. Relative to the best global program, the condition label raised the attainable aggregate gain by 723 passes on the original panels and 728 on the six-critical panels. With noisy labels, those gains fell to 160 and 161. The upper bounds describe the fixture language. The experiment’s proposer explores only edits supported by measured training cases. [Sealed per-panel results](component-conditional-edits-results-v1.json)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
PYTHONHASHSEED=0 python -m benchmarks.component_conditional_edits
PYTHONHASHSEED=0 python -m benchmarks.component_conditional_edits --execute PLAN_SHA256 --out result.json
```

Use the seal printed by the preview. Two offline runs produced byte-identical results with DNS and outbound sockets blocked. The comparison uses scripted edits and graders, with the conditional operator confined to the benchmark.
