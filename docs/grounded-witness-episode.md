# Prospective comparison of the one-admission witness episode

The archived BBH and LMentry comparison favored one-admission CPO. This protocol tests whether the advantage transfers to new ticket-routing, warehouse, and outage cases with newly generated draft prompts. The fixture rehearsal reproduced both passing and failing runs. Fresh-model performance is pending. [Archived task-budget comparison](prompteval-admission-task-budget.md) · [Sealed development plan](grounded-witness-episode-development-plan-v1.json) · [Rehearsal receipt](grounded-witness-episode-rehearsal-v1.json)

Each task gets four cycles. The responder generates one shared rewrite and repair per cycle from 16 labeled training cases and the initial prompt. All arms receive the same pair in the same order. An invalid pair leaves that cycle's roster empty. Ticket, warehouse, and outage facts are generated from the typed policy families with new case IDs and inputs. Search, admission, development scoring, and confirmation use disjoint case splits. Models can see search labels only in the shared drafting requests. Evaluation requests contain case inputs and the output schema.

| Arm | Per-cycle search cap | Validation cases | Independent admissions per task |
| --- | ---: | ---: | ---: |
| CPO with one admission | 30 | 24 | 1 |
| CPO with up to four admissions | 30 | 24 | 4 |
| Sequential GEPA 0.1.4 | 32 | 8 shared anchors | 1 |
| Batched GEPA 0.1.4 | 32 | 8 shared anchors | 1 |

Both native controls use the released GEPA engine and its full-round reserve. Their 8 anchors come from the CPO validation panel. Each cycle has its own 8 admission cases. A nomination spends an admission whether it passes or fails. The four-admission arm measures the effect of that limit. One-admission CPO is the prespecified candidate for the superiority gate.

Development scores frozen prompts twice on each of 18 cases per task. CPO must pass at least 27 of 36 per task, preserve every matched critical decision, and match or improve each control's score on every task. Against each GEPA control it must also add at least 8 passes in aggregate or preserve the score on every case and use at least 10% fewer search requests. This gate must pass under both logical search uses and distinct requests attributed to each arm. A shared draft counts toward each arm's executed cycles. The journal counts each actual responder call once across all arms, including all 12 planned drafting calls.

Independent confirmation requires an exact replay of qualifying development. Its seal binds the development plan, journal, result, selected prompts, and delivery type. It scores the same frozen prompts twice on each of 8 separate cases per task, with a 12-of-16 per-task floor and a 4-pass improvement threshold. Identical prompts share a scoring reply for each case and repeat. The run records planned limits and actual calls by role. The development ceiling is 2,712 calls. Confirmation's ceiling depends on the number of distinct prompts selected in development.

## Rehearse offline

Use a clean checkout, Python 3.12, and GEPA 0.1.4 from [the hashed requirements file](../requirements-benchmark.txt). The module's default invocation previews its seal. Its execution commands use scripted replies or a recorded journal. The source runner accepts an injected provider responder through its Python entry point. Provider wiring and model-specific pricing are outside this sealed rehearsal. [Runner](../benchmarks/grounded_witness_episode.py) · [Boundary tests](../tests/unit/test_grounded_witness_episode.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.grounded_witness_episode
python -B -m benchmarks.grounded_witness_episode \
  --fixture 0e20cd3cfb0f50c6959ec4e961513c5d6ec3ef8b6e51a0f3243aeb87bf462016 \
  --out witness-development
python -B -m benchmarks.grounded_witness_episode \
  --replay witness-development --out witness-development-replay
python -B -m benchmarks.grounded_witness_episode --development witness-development
python -B -m benchmarks.grounded_witness_episode \
  --fixture 64ff71e0d37615fcb9894aef3aca7d15cdeafdd9908137f61b892903abe3acdf \
  --development witness-development --out witness-confirmation
python -B -m benchmarks.grounded_witness_episode \
  --replay witness-confirmation --development witness-development --out witness-confirmation-replay
```

Run the development fixture with `--profile rejected` and a fresh output directory to check admission failure. This scenario rejects every eligible nomination and fails confirmation binding. In the qualifying script, CPO selects the broad repair and both GEPA arms select the narrow rewrite. Those scripted differences are inputs to the rehearsal. The confirmation fixture used exactly 144 calls, and all three fixture archives replayed byte for byte with sockets and DNS blocked.
