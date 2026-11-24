# Run the settled episode policy

`cpo.settled_episode.run_settled_episode` takes two incumbent training cases and a sequence of fixed candidate pools. It picks one search schedule from the two grades and keeps that schedule for the episode. Each cycle deploys a challenger only after independent qualification. The next cycle receives the deployed prompt as its incumbent. [Discovery and transfer study](settled-episode-refit.md)

```python
from cpo.settled_episode import EpisodeCycle, run_settled_episode

cycles = (
    EpisodeCycle(first_candidates, first_validation, first_qualification, seed=17),
    EpisodeCycle(second_candidates, second_validation, second_qualification, seed=18),
    EpisodeCycle(third_candidates, third_validation, third_qualification, seed=19),
)
result = run_settled_episode(
    starting_prompt,
    training_rows,
    cycles,
    evaluate_validation,
    probe=grade_training,
    qualify=grade_qualification,
)
deployed_prompt = result.prompt
total_evaluations = result.evaluations
```

Each cycle takes an ordered roster of up to eight challengers, 1–19 validation rows, and four qualification rows. Give every row and challenger a distinct identity across the episode. The runner checks the complete layout before invoking a callback. The published replay uses three cycles of eight challengers and six validation rows. Training and qualification callbacks return boolean grades. The validation callback returns an `Observation` with an exact boolean grade. Provide stable grades within each cycle and keep external holdout rows outside these inputs. [API implementation](../cpo/settled_episode.py)

The two training grades select the bounded opening after zero passes, misses-first uniform validation after one pass, and narrow halving after two passes. Their maximum validation charges per cycle are 19, 18, and six evaluations, respectively. Independent qualification can use up to eight additional replies per cycle. The result exposes each nomination, qualification decision, and the total across training, validation, and qualification callbacks.

## Archived verification

The packaged entry point reproduced the ordered callbacks, grades, nominations, qualification receipts, and deployments of all 2,048 sealed archive episodes. The replay totals were 53,348 held-out passes and 69,558 lookups, including 4,096 training probes. The bounded-opening baseline had 53,308 held-out passes and 72,048 lookups. These measurements describe the archived cohorts. Fresh prompt quality and performance against GEPA on independent live tasks remain open. [Sealed parity receipt](settled-episode-api-parity-v1.json)

Run the parity check with the existing benchmark dependencies and pinned GEPA 0.1.4. It reads the frozen discovery and transfer receipts and requires a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.settled_episode_api_parity --out /tmp/settled-episode-api.json
```

Two offline replays produced identical receipts with DNS and outbound sockets disabled. Storage Guard measured 9.6 GiB free. The disposable source export, wheel overlay, and publication checkout used the standing 0.2 GiB LAB exception and were removed after verification. No provider requests were made. [Parity check](../benchmarks/settled_episode_api_parity.py) · [Unit tests](../tests/unit/test_settled_episode.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
