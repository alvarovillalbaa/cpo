# Use and test the opt-in full-roster CPO runner

Import `run_full_roster_feedback_episode` from `cpo.full_roster_precheck`. It accepts the same `EpisodeCycle` inputs and `evaluate`, `probe`, and `qualify` callbacks as `run_feedback_episode`. Use it with stable replies for each prompt and case. It defers the independent qualification precheck until a nominee exists only on full quoted uniform and halving rosters. Narrow rosters, critical validation, and the fitted opening use the original route. A cycle with no nominee may contain no qualification observations. The result counts each actual callback, including validation paid before a perfect incumbent closes the gate. [Implementation](../cpo/full_roster_precheck/__init__.py)

The opt-in runner reproduced the prototype's paid trace on all 2,048 archived language episodes and all 64 Promptolution episodes. It retains the archived 4,465-lookup saving on language feedback with the same deployments. The Promptolution feedback paths match the archived baseline. A wheel built from an isolated source export exposed the new API and passed a full-roster smoke check. The existing feedback entry point and both original comparison seals reproduced. [Prototype result](witness-nomination-cost.md) · [Verification receipt](full-roster-precheck-verification-v1.json)

## Rehearsal for a future comparison

The new fixture plan compares the opt-in runner, packaged feedback, packaged settled CPO, and both native GEPA 0.1.4 controls on the same three task panels and shared draft rosters. The logical and physical ceilings are 2,151 requests each. The new feedback gate requires identical nominees, deployments, and held-out grades with a strict reduction in both search counts. The original joint gate against settled CPO and both GEPA controls also applies. [Sealed rehearsal plan](full-roster-precheck-prospective-plan-v1.json)

The fixture matched packaged feedback's decisions and held-out grades and reduced search from 108 to 101 requests under both counting methods. It passed the fixture gates against both GEPA controls. It missed the settled-CPO gate because 101 versus 111 requests at equal scores is a 9.0% saving, below the original 10% threshold. These scripted responses verify the comparison and its failure handling. A separate provider adapter and cost quote would be needed for fresh model testing. Inference remains paused.

## Reproduce offline

Use the pinned GEPA 0.1.4 wheel and Python 3.12. The archive verification also needs the pinned Promptolution corpus from the prior replay.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.full_roster_precheck_archive \
  --corpus PREDICTIONS.json --out archive-parity.json
python -B -m benchmarks.full_roster_precheck_prospective \
  --fixture f06257501aa1d800776c186b1d5c7359939223a8e6437e9466d0431cc25b7048 \
  --out full-roster-fixture
python -B -m benchmarks.full_roster_precheck_prospective \
  --replay full-roster-fixture --out full-roster-replay
```

With network disabled, the two archive verifications matched byte for byte. Two fresh fixture runs and the exact journal replay matched on the manifest, journal, results, and feedback gate. All 113 focused tests passed, including callback pricing, the critical-loss veto, and the scoped route. The old portable seal `3e34abd7a7d77514c48c5bbdd8e4bcffe676ece55c89542b0155d8b298501775` and SDK seal `7cf6946669026255b7fb38cba658445625d338dc02082fccc42743cbe86615e1` reproduced offline. Storage Guard measured 8.0 GiB free. The disposable source exports, wheel overlay, fixture archives and publication checkout fit the standing 0.2 GiB LAB exception. Teardown was verified. [Tests](../tests/unit/test_full_roster_precheck.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
