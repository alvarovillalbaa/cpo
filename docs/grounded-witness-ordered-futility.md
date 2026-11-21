# Run the witness comparison with gate-relevant scoring first

The separate ordered protocol uses the scoring order that rejected 86 of 88 scripted failures earlier in the schedule replay. It keeps the original proposal generation, search, admission, case splits, repeat count, budgets, and acceptance gates. The new order applies only once every arm has selected a prompt and search costs are fixed. It prioritizes contested critical case-repeats, scores the candidate first within each case-repeat, and defers replies used only by the descriptive arm. [Ordering study](grounded-witness-scoring-order.md) · [Development plan](grounded-witness-ordered-futility-development-plan-v1.json) · [Runner](../benchmarks/grounded_witness_ordered_futility.py)

The original benchmark and live plan retain their existing seal and execution path. The ordered protocol has its own seal. Confirmation binds the exact ordered development archive, its declared delivery, its selected prompts, and the ordered confirmation request schedule. It requires a complete qualifying development panel. The CLI exercises the protocol with fixtures or replays. The Python entry point accepts a caller-supplied responder for a separately authorized execution.

The qualifying and rejected paths keep the original journal format. A qualifying run records the full panel. An early rejection records the paid prefix, the first unsent request hash, and the verdict under the best possible completion. Replay verifies the request sequence and all three archive files byte for byte.

## Rehearsal

| Fixture | Original scoring requests | Ordered scoring requests | Decision |
| --- | ---: | ---: | --- |
| Qualifying development | 288 | 288 | Qualified |
| Development with no qualifying admission pattern | 0 | 0 | Rejected before scoring |
| Outage failure in development | 209 | 128 | Rejected early |
| Qualifying confirmation | 128 | 128 | Qualified |
| Outage failure in confirmation | 93 | 55 | Rejected early |

The outage fixture fails every outage scoring reply and leaves search replies intact. Both development runners selected the same prompts, charged the same search requests, and wrote identical search journal entries. The qualifying ordered run used the same physical scoring request and reply pairs in its new sequence. With DNS and sockets blocked, 41 targeted tests passed and five ordered archives reproduced byte for byte. The rehearsal made zero provider requests. The existing live plan preview reproduced byte for byte. Storage Guard measured 6.2 GiB free. The bounded export, fixture archives, and publication worktree used the standing 0.2 GiB LAB exception. [Journal and confirmation tests](../tests/unit/test_grounded_witness_ordered_futility.py)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. The development seal below also accepts `--profile outage-scoring-failure` or `--profile rejected-admission` in a fresh directory.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.grounded_witness_ordered_futility
python -B -m benchmarks.grounded_witness_ordered_futility \
  --fixture ce048ab5da16f4b3a4162ddc67097a6e16717826afb2236170b08a6b63a866dc \
  --out ordered-development
python -B -m benchmarks.grounded_witness_ordered_futility --development ordered-development
python -B -m benchmarks.grounded_witness_ordered_futility \
  --fixture cce81db7764455d5dc630fef7f216f2abc95a4d58705d0731373d360b135d3b7 \
  --development ordered-development --profile outage-scoring-failure --out ordered-confirmation
python -B -m benchmarks.grounded_witness_ordered_futility \
  --replay ordered-confirmation --development ordered-development --out ordered-confirmation-replay
```
