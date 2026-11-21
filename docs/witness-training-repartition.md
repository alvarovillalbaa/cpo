# Spread training contexts across proposal calls

Rearranging the same 192 training examples reduced missed synthetic stress checks from 75 to 69. The four 16-example blocks per task still used 37,602 serialized input bytes in total. The earlier stress replay showed that some contexts were absent even from full blocks. This replay uses the same examples, grader, and stress cases to test how much coverage their allocation can recover. [Earlier context stress study](witness-training-context.md) · [Replay runner](../benchmarks/witness_training_repartition.py)

The selector exchanges two examples with the same criticality only if both blocks keep every label and declared policy fault that they originally exposed. It maximizes total context coverage first, then favors coverage in the weakest individual blocks and pairs. It uses first-pair and first-block coverage to break remaining ties. It stops when no single permitted exchange improves that ordering. Development, confirmation, and stress cases enter only the final measurement.

| Task | Distinct contexts across individual blocks | Fewest contexts in any pair | Contexts in the first pair | Stress misses across blocks |
| --- | ---: | ---: | ---: | ---: |
| Ticket | 53 → 59 | 18 → 19 | 19 → 20 | 43 → 37 |
| Warehouse | 64 → 64 | 16 → 22 | 24 → 23 | 32 → 32 |
| Outage | 64 → 64 | 16 → 16 | 16 → 16 | 0 → 0 |

The distinct-context total counts a context once per block. Five ticket exchanges raised the ticket total to 59, the maximum allowed by the number of training examples available per context. Warehouse and outage already reached their bounds. Seven warehouse exchanges improved its weakest pair from 16 to 22 contexts while reducing the first pair from 24 to 23. Warehouse stress misses stayed constant, including when measured over all pairs. Outage needed no exchanges.

Across individual blocks, missed development checks fell from 55 to 52 and missed confirmation checks fell from 18 to 14. Across all six pairs per task, stress misses fell from 39 to 37 while the development and confirmation counts stayed at 27 and 4. Each miss counts one scoring case whose context was absent from one block or pair. The highest input size across the 12 blocks fell from 3,669 to 3,668 serialized bytes. Per-request provider token counts and live proposal quality remain unmeasured. Live plans retain their sealed allocations. [Exact block assignments and measurements](witness-training-repartition-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and outbound sockets blocked, 42 targeted tests passed and two replays matched byte for byte. A stale seal was rejected and the prospective live development preview matched its archived manifest. Storage Guard measured 6.1 GiB free. The 39 MiB source and wheel overlay and the bounded publication worktree used the standing 0.2 GiB LAB exception. The replay sent zero provider requests. [Exchange constraint tests](../tests/unit/test_witness_training_repartition.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_training_repartition
python -B -m benchmarks.witness_training_repartition \
  --execute 37fefee370de26a90a8fb140ace03c9c19dd2ce715cef0f0093bf564266f323f \
  --out NEW_REPORT.json
```
