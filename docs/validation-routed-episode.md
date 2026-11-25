# Run full-roster CPO with a validation-routed opening

`run_validation_routed_episode` chooses the opening schedule from the first incumbent validation replies. A miss chooses uniform validation. After one pass it reads a second case, and two passes select narrow halving. The opening buys zero training replies. It reuses any routing reply requested by the selected screen and counts all lookups, including unused routing replies, against the 19-lookup first-cycle validation cap. Independent qualification still determines promotion. [Implementation](../cpo/full_roster_precheck/validation_routing.py) · [Measured replay](validation-routed-opening.md)

```python
from cpo.full_roster_precheck.validation_routing import run_validation_routed_episode
from cpo.settled_episode import EpisodeCycle

cycle = EpisodeCycle(candidates, validation_rows, qualification_rows, seed=17)
result = run_validation_routed_episode(
    starting_prompt, (cycle,), evaluate_validation, qualify=grade_qualification,
)
deployed_prompt = result.prompt
total_lookups = result.evaluations
```

Supply at least one cycle. Each cycle accepts up to eight ordered challengers, 1–19 validation rows, and four qualification rows. The runner validates the entire episode before a callback and requires distinct row IDs and candidate prompts. Validation returns an `Observation`, and qualification returns a boolean. Keep grades stable and holdout rows outside the episode. When the opening has no challengers, only one validation row, or any critical validation row, the runner uses the fixed uniform policy without routing reads. Later cycles follow the existing feedback schedule after a rejection. [Fixed-opening runner and feedback behavior](fixed-opening-episode.md)

The packaged route reproduced the sealed benchmark across 2,048 language episodes and 3,040 math audit trials. The language replay measured 103 more passes and 2,803 fewer lookups than adaptive CPO. On rotated ARC-AGI with eight challengers it measured 264 more passes and 124 fewer lookups than its calibrated GEPA control. The replayed AIME comparisons remain inconclusive. Fresh-model validation remains open. [Sealed receipt](validation-routed-opening-v1.json)

## Verify offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel for archive parity.

```sh
PYTHONHASHSEED=0 python -B -m pytest -q \
  tests/unit/test_validation_routed_episode.py \
  tests/integration/test_validation_routed_archive_parity.py
```

All 48 focused tests passed. The parity test reproduced the prior trace hashes, scores, lookup totals and comparator effects. A wheel installed into a disposable target selected uniform, independently qualified a challenger and reconciled nine lookups. Verification blocked sockets and reproduced the three existing comparison seals. Storage Guard measured 9.1 GiB free. The isolated source, wheel, and publication worktree used 124 MiB under the standing 0.2 GiB LAB exception. [Unit tests](../tests/unit/test_validation_routed_episode.py) · [Archive parity test](../tests/integration/test_validation_routed_archive_parity.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
