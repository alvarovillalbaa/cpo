# Seal confirmation across every first-gain policy regime

The independent-proposal development plan compares five optimizers. Its existing eight-case reserve for each task covers only eight warehouse regimes and eight outage regimes. This confirmation design creates one case per defined regime and scores each case twice. The inputs and case IDs are disjoint from every role in the published development layout, including its original reserve. Seven of the eight ticket cases reuse a topic and channel combination seen in training. [Development comparison](first-gain-independent-proposals.md) · [Earlier regime analysis](grounded-witness-regime-coverage.md)

| Task | Development holdout regimes | Original reserve regimes | New confirmation cases | Critical cases | Exact pass floor across two repeats |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ticket | 8 | 8 | 8 | 3 | 12/16 |
| Warehouse | 18 | 8 | 24 | 16 | 36/48 |
| Outage | 16 | 8 | 16 | 8 | 24/32 |

The confirmation ceiling is **576 generations** for 48 cases, two repeats, and at most six distinct prompts per task, including the initial prompt. Exact matching requests may share a reply. Grading requires a complete ledger, a 75% candidate score on each task, the paired quality and cost gates on both development search tallies, and at least one exact candidate pass per regime case. The scorer rejects a missing arm, case, repeat, or Boolean grade. [Panel and frozen gate](first-gain-regime-confirmation-v1.json)

The rehearsal injected one schema-valid policy error into each regime. When all arms shared a persistent error, the paired comparison passed all 48 fixtures and the per-regime requirement rejected all 48. When all arms shared only one failed repeat, all 48 fixtures qualified. The paired comparison caught all 48 persistent candidate-only errors. These tests measure the gate's ability to detect the defined synthetic faults. Binding model prompts and costs requires a complete, qualifying development archive. [Runner](../benchmarks/first_gain_regime_confirmation.py) · [Tests](../tests/unit/test_first_gain_regime_confirmation.py)

The offline binding rehearsal checks the complete development archive and the exact confirmation request schedule. [Binding and replay](first-gain-bound-confirmation.md)

## Reproduce offline

Run without arguments to preview the seal. Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel for the accompanying benchmark tests.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_regime_confirmation \
  --fixture 52c2bc5f86e338c393aeebea21c24e5a1d3510b09e97845d71d312ffe7090170 \
  --out NEW_REPORT.json
```

Both replays blocked sockets and DNS and produced byte-identical receipts with SHA-256 `fc04fc18069c29b0a6539025d050d5f2d7df095b9a86f30bd0522fa13dde3ec1`. All 12 current focused tests passed. The older witness tests require their original source seal. All eight passed on an export of revision `5fed91b`. The CLI rejected a stale seal and an occupied output path. Storage Guard measured 8.5 GiB free. The temporary exports and verification worktree occupied 139 MiB under the standing LAB exception. Zero provider requests were sent. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
