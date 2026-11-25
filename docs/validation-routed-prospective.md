# Rehearse a matched comparison of validation-routed CPO

The sealed comparison runs packaged validation-routed CPO, adaptive full-roster CPO, settled CPO, and the pinned sequential and batched GEPA controls. It uses the same three tasks, three cycles, case splits, and grader as the settled comparison. The four controls keep their seeded order. The routed arm runs last on the same draft rosters and makes its own validation and admission decisions. Each non-draft reply can be reused only for the same task, role, prompt, case, and repeat. Final scoring sends a separate request for every distinct selected prompt on each holdout case and repeat. [Runner](../benchmarks/validation_routed_prospective.py) · [Original settled comparison](settled-episode-prospective.md) · [Routed API](validation-routed-episode.md)

The fixture plan reserves room for new validation, admission, and holdout requests when the routed arm diverges. The routed arm buys zero training probes and has a limit of 19 validation lookups and eight independent admission lookups per cycle. The maximum is 2,145 physical requests across all three tasks. The inherited gate compares routed CPO against the initial prompt and all four controls. It requires the per-task score floor and preservation on critical cases, then applies the score-gain or efficiency test to both logical and attributed search counts. [Sealed plan](validation-routed-prospective-plan-v1.json)

| Role | Request ceiling | Scripted physical requests |
| --- | ---: | ---: |
| Shared drafting | 36 | 36 |
| Training and validation | 1,101 | 200 |
| Admission | 360 | 52 |
| Holdout scoring | 648 | 252 |
| **Total** | **2,145** | **540** |

The fixture exercised both opening schedules. On outage, routed CPO promoted a different prompt from adaptive CPO. Both selected prompts received full holdout scoring. The routed arm needed six additional validation requests and six additional admission requests beyond the replies available from the controls. It used 97 attributed search requests against 120 for adaptive CPO, 123 for settled CPO, 191 for sequential GEPA, and 243 for batched GEPA. All five arms tied on scripted holdout score, so the gate passed on efficiency. The scripted scores verify execution and accounting. Fresh-model performance remains open. [Fixture receipt and archive hashes](validation-routed-prospective-rehearsal-v1.json)

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. The CLI without arguments previews the seal.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.validation_routed_prospective \
  --fixture b155168f99831e8597f1d5a8b0f581f34159b0425f0f38b49ae9f3a4d8eca70c \
  --out NEW_FIXTURE
python -B -m benchmarks.validation_routed_prospective \
  --replay NEW_FIXTURE --out REPLAY
```

Two fixture runs and the exact journal replay matched byte for byte on all four archive files. All 35 offline tests passed, including checks for a stale seal, an altered admission repeat, an incorrect holdout merge, and a model-delivered source manifest. The fixture used zero provider requests. Storage Guard measured 9.1 GiB free. The isolated source export, GEPA overlay, fixture archives, and publication worktree fit in 128 MiB under the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_validation_routed_prospective.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
