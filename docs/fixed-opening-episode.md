# Run full-roster CPO with a calibrated opening

Use `run_fixed_opening_episode` when you have chosen an opening schedule before the episode. The runner buys zero training replies. It uses the existing full-roster validation policy and independent qualification before deploying a new prompt. After a rejected finalist, the next cycle uses the same follow-up as the adaptive feedback runner. [Implementation](../cpo/full_roster_precheck/fixed_opening.py) · [Adaptive runner](full-roster-precheck.md)

```python
from cpo.full_roster_precheck.fixed_opening import run_fixed_opening_episode
from cpo.settled_episode import EpisodeCycle

cycle = EpisodeCycle(candidates, validation_rows, qualification_rows, seed=17)
result = run_fixed_opening_episode(
    starting_prompt,
    (cycle,),
    evaluate_validation,
    schedule="uniform/8/18",
    qualify=grade_qualification,
)
deployed_prompt = result.prompt
total_lookups = result.evaluations
```

`FIXED_OPENING_SCHEDULES` lists the fitted opening, uniform validation, and narrow successive-halving options. Use separate calibration cases to choose a schedule and keep final scoring outside the supplied validation and qualification rows. Each cycle accepts up to eight ordered challengers, 1–19 validation rows and four qualification rows. The entire episode requires distinct row IDs and prompts. The callbacks have the full-roster signatures. Each validation lookup returns an `Observation` and each qualification lookup returns a boolean. The receipt records the schedule and disposition of each cycle and counts every callback it made.

On archived ARC-AGI trials starting at the original prompt, both calibration folds chose `uniform/8/18`. It scored 57 and 70 additional held-out passes and used 143 and 233 fewer lookups than adaptive CPO with four and eight challengers, respectively. The choice varied across rotated starts and AIME. The measured benefit applies to the recorded cases. A fresh model comparison remains open. [Cross-fit case replay](full-roster-fixed-opening.md)

## Verify offline

```sh
PYTHONHASHSEED=0 python -B -m pytest -q \
  tests/unit/test_fixed_opening_episode.py \
  tests/integration/test_fixed_opening_archive_parity.py
```

The integration tests replay all three fixed schedules on 3,040 AIME and ARC-AGI trials. They match the prototype's decisions, ordered callbacks, charged lookups and held-out grades, then reconcile the published fold totals. The full verification passed 37 focused tests and reproduced the settled, full-roster, and shared-reply comparison seals. A local wheel installed into a disposable target independently qualified a challenger in seven lookups. Both checks ran with sockets blocked. Storage Guard measured 9.3 GiB free. The source export, wheel, and isolated publication worktree totaled 124 MiB under the standing 0.2 GiB LAB exception. [Unit tests](../tests/unit/test_fixed_opening_episode.py) · [Archive parity test](../tests/integration/test_fixed_opening_archive_parity.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
