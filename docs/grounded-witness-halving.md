# Test the capped fallback alongside the original witness policy

This prospective comparison adds the capped Halving fallback and two Halving-only controls to the original typed benchmark. It retains the original starting prompt, ticket, warehouse and outage case splits, shared drafts, CPO arms, and GEPA controls. It uses the same cohort as the original prospective plan. Each protocol binds a separate confirmation panel within its own run. [Original benchmark](grounded-witness-episode.md) · [Recorded fallback results](bounded-halving-fallback.md) · [New development plan](grounded-witness-halving-development-plan-v1.json)

The hybrid reuses the one-admission CPO path. If that path starts an independent proof, the hybrid inherits its outcome, including a rejection. If the witness path finishes without a proof, the hybrid uses the same draft pairs and validation grades to try certified Successive Halving at logical cap 8. A hard limit of 16 additional validation grades applies across all four fallback cycles for a task. A completed challenger gets at most one independent proof. A capped search cannot start proof. The cap-8 and cap-12 Halving-only controls use the same certificate-based selector and admission rules. [Selector](../cpo/halving/__init__.py) · [Comparison runner](../benchmarks/grounded_witness_halving.py)

The hybrid qualifies against original one-admission CPO, sequential GEPA, batched GEPA, and both Halving-only controls. The four-admission CPO arm remains descriptive. The task floor and matched critical-case protection come from the original protocol. Against each control, the hybrid must preserve each task's score and add eight development passes in aggregate or preserve each case's score while saving at least 10% of search uses. The comparison applies the gate to both logical search uses and distinct requests attributed to each arm. Validation grades reused by the hybrid count once in its own attributed cost.

The development ceiling is **3,612** responder calls. That includes 12 shared drafting calls, 1,776 evaluation calls, 960 admission calls, and 864 development-scoring calls. The confirmation seal binds the three exact development artifacts, declared delivery, and selected prompts. Its call count depends on the number of distinct prompts. Confirmation scores those frozen prompts on disjoint cases without new drafts, search, or admissions.

## Offline rehearsal

The qualifying fixture made 660 responder calls and recovered the scripted ticket task using two validation grades beyond those already used by the witness path. A separate 128-call fixture confirmation qualified. The rejected development fixture spent the witness admission, skipped fallback, and failed confirmation binding. All three archives replayed byte for byte with sockets and DNS blocked. The original arms matched their earlier runner on the same fixture inputs. These scripted outcomes exercise the protocol. Fresh-model performance remains open. [Fixture receipt](grounded-witness-halving-rehearsal-v1.json) · [Boundary tests](../tests/unit/test_grounded_witness_halving.py)

## Reproduce

Use a clean checkout, Python 3.12, and GEPA 0.1.4 from the hashed requirements. The CLI previews and replays the protocol or invokes scripted replies. A provider responder can use the Python entry point. [GEPA requirement](../requirements-benchmark.txt)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.grounded_witness_halving
python -B -m benchmarks.grounded_witness_halving \
  --fixture a051692499b42db79f93ae2d7a5b5e4c3845b16c915a8238791d814af3567bca \
  --out fallback-development
python -B -m benchmarks.grounded_witness_halving \
  --replay fallback-development --out fallback-development-replay
python -B -m benchmarks.grounded_witness_halving --development fallback-development
python -B -m benchmarks.grounded_witness_halving \
  --fixture 48f96e529653f7b3c3455d4b3862dca65a4a949a7ef11f636371fa61ac76beee \
  --development fallback-development --out fallback-confirmation
```
