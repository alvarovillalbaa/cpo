# Use the two-witness fixed-pool selector

`select_two_witness_pool` takes an incumbent followed by challengers, a validation panel, and an evaluator that returns an `Observation` with an exact Boolean grade. It ranks challengers using a shared incumbent miss and pass, then completes exact validation for up to two finalists. A challenger must strictly exceed the incumbent's validation score and preserve its critical passes. [Selector](../cpo/two_witness_pool/__init__.py)

```python
from cpo.paired_qualification import certify_paired_qualification
from cpo.two_witness_pool import select_two_witness_pool

selection = select_two_witness_pool(
    (incumbent, *challengers), validation_rows, evaluate, metric_limit=42,
)
next_prompt = incumbent
if selection.prompt != incumbent:
    decision = certify_paired_qualification(
        incumbent, selection.prompt, qualification_rows, qualify, seed=17,
    )
    next_prompt = decision.prompt
```

Use distinct row IDs and hold qualification cases out of validation. The search limit counts calls to `evaluate`; a paid prompt and row pair is reused within the call. Reserve training and qualification lookups separately. With two or fewer challengers, a one-row panel, or a cap too small to fund the full screen and finalist suffixes, the selector uses the bounded exact pool race. The returned `PoolResult` contains the selected prompt, its exact validation score, and the callback count.

## Archived parity

The replay substitutes the public selector for the earlier benchmark implementation and retains the archived training corroboration and expected-cost qualification. It verifies paid search and proof paths, nominees, deployments, held-out replies, and lookup counts on every panel. The example above composes the selector with the standard qualification API. The archived cost comparisons additionally include the study's training and qualification schedule. [Screening study](recorded-shortlist-screen-order.md) · [Held-out model study](recorded-shortlist-model-transfer.md)

| Archive | Model panels | Trials | Held-out passes | Paid lookups |
| --- | ---: | ---: | ---: | ---: |
| Screening study | 44 | 1,408 | 15,395 | 43,116 |
| Held-out model study | 32 | 1,024 | 11,415 | 29,351 |

The source export and a clean target installation of the built wheel produced byte-identical parity reports. All 70 targeted tests and five subtests passed with sockets and DNS blocked. The selector lives in a separate packaged submodule because the historical live plan hashes the top-level CPO modules. The ordered live plan preview still matches its published seal. Storage Guard measured 4.5 GiB free and the bounded wheel and replay used the standing 0.2 GiB LAB exception. The replay sent zero provider requests. [Parity receipt](recorded-two-witness-pool-parity-results-v1.json) · [Selector tests](../tests/test_two_witness_pool.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_two_witness_pool_parity
python -B -m benchmarks.recorded_two_witness_pool_parity \
  --execute 00b3ee9103ecb4f91ff53458f2483993d1d113a1c9a91d2630ab46b173d8d7f8 \
  --out NEW_REPORT.json
```
