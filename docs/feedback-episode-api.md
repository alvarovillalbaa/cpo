# Run a CPO episode with qualification feedback

Use `cpo.feedback_episode.run_feedback_episode` to try the frozen rejected-finalist policy with your own candidate pools and graders. The first cycle uses the opening schedule selected by two incumbent training grades. If a nominee fails independent qualification, the next cycle uses the follow-up schedule for that opening state. A skipped cycle keeps the incumbent and incurs zero callbacks. Each later cycle makes the same decision from the immediately preceding result. [Feedback discovery and transfer](settled-episode-qualification-feedback.md)

```python
from cpo.feedback_episode import run_feedback_episode
from cpo.settled_episode import EpisodeCycle

cycles = (
    EpisodeCycle(first_candidates, first_validation, first_qualification, seed=17),
    EpisodeCycle(second_candidates, second_validation, second_qualification, seed=18),
    EpisodeCycle(third_candidates, third_validation, third_qualification, seed=19),
)
result = run_feedback_episode(
    starting_prompt,
    training_rows,
    cycles,
    evaluate_validation,
    probe=grade_training,
    qualify=grade_qualification,
)
deployed_prompt = result.prompt
paid_callbacks = result.evaluations
actual_schedules = result.cycle_schedules
```

The callbacks and row layout follow the settled episode API. Supply two training rows and use disjoint row IDs and distinct prompts across the entire episode. Each cycle accepts up to eight challengers, 1–19 validation rows, and four independent qualification rows. The runner checks the complete layout before calling a grader. `result.schedule` records the opening selection and `cycle_schedules` records the actual route. A skipped cycle has zero evaluations, no finalist, and no qualification receipt. [Settled episode callback contract](settled-episode-api.md) · [Feedback implementation](../cpo/feedback_episode.py)

## Archived parity

The packaged API matched the complete ordered callback trace, grades, nominations, qualification decisions, schedules, and deployments across 2,048 archived episodes. It reproduced 53,345 held-out passes on 68,582 lookups. The 735 schedule switches include 80 skipped cycles. The settled runner remains available as the original policy, and its sealed verification receipt reproduced byte for byte. Fresh live performance remains unverified. [Feedback parity receipt](settled-episode-feedback-api-parity-v1.json) · [Original receipt](settled-episode-api-parity-v1.json)

Run the check with the pinned GEPA 0.1.4 benchmark environment and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.settled_episode_feedback_api_parity --out /tmp/cpo-feedback-api.json
```

Two offline runs produced identical receipts with sockets and DNS blocked. Eighty targeted source tests passed. An offline-built wheel contained the public module and passed all seven API tests from a separate directory. Storage Guard measured 9.5 GiB free. The disposable source, wheel, and publication checkout fit the standing 0.2 GiB LAB exception and were removed after verification. No provider requests were made. [Replay script](../benchmarks/settled_episode_feedback_api_parity.py) · [API tests](../tests/unit/test_feedback_episode.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
