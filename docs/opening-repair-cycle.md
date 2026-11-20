# Run the opening screen with one funded repair

Use the opt-in `run_opening_repair_cycle` API when a rewrite and repair are already available and a later proposal can fix errors found in training. It starts with the [opening screen](opening-screen-cycle.md) and reserves the cost of validating one repair before reading any training probes.

```python
from cpo import ProposalPair
from cpo.opening_repair_cycle import run_opening_repair_cycle

result = run_opening_repair_cycle(
    incumbent,
    training_rows,
    validation_rows,
    qualification_rows,
    evaluate,
    propose,
    opening_pair=ProposalPair(rewrite, repair),
    metric_limit=56,
    qualify=qualify,
    diagnostic_prompt=instruction_only,
    max_training_probes=2,
)

next_incumbent = result.prompt
```

The optional `diagnostic_prompt(full_prompt)` callback returns the prompt for the training probes. For a program with demonstrations, it can return the instruction with an empty demonstration bundle. The evaluator receives that variant on training. `propose(parent, feedback, history, width)` receives the complete parent, the paid training observations, an empty history, and a width of one. It can return a prompt, a `ProposalPair`, a `ProposalBatch`, or an iterable of prompts. The cycle considers the first proposal. Omitting the transform evaluates the complete parent on training. [Package API](../cpo/opening_repair_cycle.py)

The cycle considers a repair after an opening nominee has errors on full validation and the budget can fund a probe and a full repair check. A failed training probe triggers the proposal. The repair must gain exact passes over the opening nominee, preserve its critical passes, and keep or raise every validation family’s score. One final independent qualification compares the selected nominee with the starting incumbent. A rejected or undecided proof retains that incumbent.

Use `result.search.evaluations` for validation and training lookups, `result.search.reflections` for later proposal calls, and `result.qualification_evaluations` for qualification lookups. Count the supplied opening’s generation separately. The `targeted-repair` event records the repair status, additional lookups, and probe outcomes when an opening advances to full validation and becomes the nominee. The separate `qualification_limit` controls how many qualification lookups the certificate may dispatch.

## Verification

The clean source and a separately installed wheel reproduced all 72 sealed typed settings, including request order, lookup counts, final prompt choices, and holdout scores. Thirteen focused tests passed in each environment. The tests cover diagnostic isolation, funding, critical-pass protection, callback accounting, and a zero qualification allowance. [Sealed diagnostic benchmark](opening-repair-diagnostic.md) · [Replay artifact](opening-repair-api-replay-v1.json) · [Verification receipt](opening-repair-api-verification-v1.json)

The controlled typed benchmark passed both GEPA gates at cap 56. Its additional seeds reused some earlier fixture inputs. Live proposal quality and provider costs remain unmeasured.

The policy-transfer fixture recovered single omissions and exposed the limit of one repair when two rules were missing. [Transfer benchmark](opening-repair-policy-transfer.md)

## Reproduce offline

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_repair_api_replay
PYTHONHASHSEED=0 python -B -m benchmarks.opening_repair_api_replay \
  --execute bcdafc8310980a55168e8e3df100b6c86d4f84a5c50521a67463a1cfb8dbea8a \
  --out NEW_REPORT.json
```

Both replays blocked sockets and DNS and produced byte-identical reports. The wheel build and installation used local tooling with the package index disabled. The CLI rejected a stale seal and preserved an existing result. Storage Guard measured 4.7 GiB free. The 28.4 MB export, build, and install directory was removed under the standing LAB exception. [Replay runner](../benchmarks/opening_repair_api_replay.py) · [Focused tests](../tests/unit/test_opening_repair_cycle.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
