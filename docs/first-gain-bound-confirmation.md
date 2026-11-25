# Bind independent confirmation to a qualifying development archive

The offline confirmation runner reconstructs the published 48-case panel and exactly replays the independent-proposal development archive. Development must qualify on both search-cost measures. The bound seal fingerprints the four development files, the selected prompts, both search-cost tallies, and the exact confirmation request schedule. [Confirmation cases and scoring rules](first-gain-regime-confirmation.md) · [Runner](../benchmarks/first_gain_bound_confirmation.py)

The schedule assigns one grade to every arm on every case and repeat. Identical prompts share one request within that case and repeat. The rehearsal scored 576 distinct requests per profile. A separate test assigned two controls the same ticket prompt and verified that the schedule dropped to 560 requests while preserving all 576 grades.

| Scripted confirmation profile | Paired gate | Per-regime check | Overall |
| --- | --- | --- | --- |
| Candidate gains four passes over each control | Pass | Pass | Pass |
| All arms share one failed repeat on a warehouse case | Pass | Pass | Pass |
| All arms fail both repeats on that warehouse case | Pass | Fail | Fail |

The verifier builds a scripted development archive with a qualifying holdout gain. The published tied fixture remains unqualified. Tests reject missing and failed development archives, a falsified development verdict, a model-delivered manifest, stale seals, live archive paths, and an altered confirmation request. Binding actual model development still requires a provider-backed development archive and its verifier. [Sealed fixture receipt](first-gain-bound-confirmation-rehearsal-v1.json) · [Focused tests](../tests/unit/test_first_gain_bound_confirmation.py)

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. The verifier builds disposable development and confirmation fixtures and replays each archive.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_bound_confirmation --verify
```

To inspect a qualifying fixture you already have, pass `--development DEVELOPMENT`. Use its printed seal with `--fixture PLAN_SHA256 --profile PROFILE --out CONFIRMATION` to retain the confirmation files. To verify those files, pass `--development DEVELOPMENT --replay CONFIRMATION --out REPLAY`.

Two verification runs produced byte-identical receipts at SHA-256 `5f417bb9bb824ead6c07e75fddbe886d9772ebd8c40ade90db88d4b1511fafc3`. The bound CLI preview, fixture and replay matched, and all 17 focused tests passed. The verification blocked sockets and DNS and sent zero provider requests. Storage Guard measured 8.6 GiB free. The temporary fixtures, source export, and publication worktree occupied 139 MiB under the standing LAB exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
