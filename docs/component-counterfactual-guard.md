# Counterfactual checks before promoting scoped edits

Scoped edits can fix one input condition while preserving behavior elsewhere. When the condition label is wrong, the new edit may run on a critical case it was meant to leave alone. This experiment tested whether a small number of targeted validation probes could catch that failure before selecting a scoped winner. [Prior label-shift study](component-conditional-edits.md)

## Protocol

CPO and both official GEPA 0.1.4 controls used the same conditional proposer. Each algorithm ran its ordinary search at cap 96 or 144. The three policies reused the measured search evidence and selected from the same result:

- **Search** kept the ordinary winner.
- **Clean gate** required a scoped winner to prove a strict nominal pass gain over the strongest fully observed global candidate and preserve every critical validation pass it achieved. The gate used paid observations only.
- **Counterfactual gate** also tested the scoped winner on those same protected cases with the condition label reversed. The global fallback is invariant to that label in this fixture. The challenger needed to pass each probe. The gate could spend only the evaluations left by search. It selected the global fallback if a required check failed or could not be funded.

The trial used 32 new seeds, four profiles, and two validation designs. Within a trial, the three policies shared training, validation, holdout, search, and the cap. Holdout checks scored each selected program with the clean label, the previous seven-label shift, and both possible labels on each input. In the last column, a case counts as passed only if it passes under both labels. [Challenger certificate](../cpo/challenger.py)

## Results

Each CPO row covers 9,216 held-out cases. Calls include search evaluations, proposal slots, and any additional guard probes.

| Panel | Policy | Clean passes | Shifted passes | Passes under both labels | Calls |
| --- | --- | ---: | ---: | ---: | ---: |
| Original | Search | 6,504 | 6,486 | 6,384 | 25,638 |
| Original | Clean gate | 6,522 | 6,506 | 6,406 | 25,638 |
| Original | Counterfactual gate | 6,446 | 6,436 | 6,414 | 25,712 |
| Six critical | Search | 6,625 | 6,587 | 6,375 | 26,102 |
| Six critical | Clean gate | 6,593 | 6,557 | 6,351 | 26,102 |
| Six critical | Counterfactual gate | 6,473 | 6,451 | 6,367 | 26,238 |

The clean gate certified 66 scoped CPO winners. The counterfactual gate kept 38, rejected 20 after an observed flipped-label regression, and fell back on eight that could not be certified within budget. Compared with the clean gate, it gained 24 passes under both labels and lost none of that baseline’s matched critical passes under that metric. It lost 196 nominal passes and 176 passes under the seven-label shift. It used 210 extra probes inside the original evaluation caps.

The guard still missed the contextual critical-case gate against both GEPA controls, including when GEPA used the same guard. It protects measured passes of a particular fallback on a particular panel. The benchmark results do not support adding it to the default search policy. [Sealed results](component-counterfactual-guard-results-v1.json)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
PYTHONHASHSEED=0 python -m benchmarks.component_counterfactual_guard
PYTHONHASHSEED=0 python -m benchmarks.component_counterfactual_guard --execute PLAN_SHA256 --out result.json
```

Use the seal printed by the preview. The benchmark uses scripted edits and scoring. Exact details include the fallback, each measured counterfactual probe, and the disposition of the gate. Both runs produced byte-identical results with DNS and outbound sockets blocked.
