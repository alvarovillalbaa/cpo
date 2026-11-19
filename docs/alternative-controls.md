# Scored history and demonstration controls

This deterministic comparison tests whether CPO can spend fewer evaluations when a program combines an instruction with labeled examples. Every arm uses the same three seeds, typed policy grader, training and validation cohorts, and evaluation caps. A single fixture response supplies the starting rewrite and repair. The shared opening counts as one search call for each arm. A case receives one holdout score per arm, and identical programs share the same response for that case.

The fixture samples a common bundle of four labeled training examples for the demonstration-aware arms. Their programs can use the bundle to fill a categorical field left open by the instruction when the relevant attributes match and the matching examples agree. The fixture tests data flow and budget allocation with a fixed interpretation of demonstrations. The holdout uses 162 seeded case identities across nine task panels. The seeds reuse policy patterns and the results describe this fixture.

| Arm | Search method |
| --- | --- |
| CPO, instructions | Released CPO with field credit and reflective instruction updates |
| CPO, joint | Released CPO with field credit and a choice of keeping or dropping the shared demonstrations during later reflection |
| GEPA, joint | Official GEPA 0.1.4, rewrite-first sequential, with the shared demonstrations and exact-first field scores |
| Scored history | Full validation of each instruction, with the score history sorted from worst to best and the highest-scoring instruction as the refinement parent |
| Instruction and demonstration grid | Full validation of the shared rewrite and repair crossed with an empty or labeled bundle, in a fixed order |

The scored-history control isolates a mechanism from OPRO. The fixture refines the selected parent with scripted field repairs. The grid control isolates MIPROv2’s joint instruction and demonstration search space. Official MIPROv2 also uses bootstrapped demonstrations, a model-based instruction proposer, and Bayesian search. Those stages and full model-backed OPRO remain outside this fixture. [OPRO paper](https://arxiv.org/abs/2309.03409) · [DeepMind implementation](https://github.com/google-deepmind/opro/blob/main/opro/optimization/opt_utils.py) · [MIPRO paper](https://arxiv.org/abs/2406.11695) · [DSPy MIPROv2](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/MIPROv2.md)

## Results

| Arm | Cap 40 passes / calls | Cap 56 passes / calls |
| --- | ---: | ---: |
| CPO, joint | 162 / 288 | 162 / 288 |
| CPO, instructions | 162 / 333 | 162 / 333 |
| GEPA, joint | 151 / 246 | 162 / 298 |
| Scored history | 54 / 297 | 162 / 375 |
| Instruction and demonstration grid | 151 / 261 | 151 / 297 |

The gate requires at least 14 of 18 passes in each task panel, preserved totals in each matched panel, and no matched critical losses. It also requires eight added passes without extra calls or at least 10% fewer calls. At the primary cap of 56, CPO with demonstrations cleared the gate against instruction-only CPO, scored history, and the instruction and demonstration grid. It tied GEPA in every panel with no matched critical losses and saved 3.4% of search calls, short of the 10% threshold. At cap 40, its 11 additional passes against GEPA and the grid came at higher call counts. The bundled demonstrations reduced CPO’s own calls by 13.5% at both caps.

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.alternative_controls
python -m benchmarks.alternative_controls --out alternative-controls.json
python -m benchmarks.alternative_controls --replay alternative-controls.json
```

Two runs produced identical reports with sockets blocked, and replay checked the plan, scores, and per-arm search digests. The plan SHA-256 is `efc42126d6943499b6abe0a64ab3733e19c91f5025da4dc5b511455be4ab56a2`. The report SHA-256 is `a915bba9c7a080335e0da3c2e2a27996893cd753a4f6aa2c8455e59bbfc7966e`. [Runner](../benchmarks/alternative_controls.py) · [Verification tests](../tests/test_alternative_controls.py)
