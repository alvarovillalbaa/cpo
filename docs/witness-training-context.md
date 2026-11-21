# Check compact training blocks for context-specific blind spots

The earlier compact training blocks kept every declared label and single-rule fault distinction. This replay tests separate errors that occur only in a specific context. Ticket uses topic and channel. Warehouse uses stock sign, inspection, tier, and site. Outage uses duration, plan, whether the fee cap binds, and evidence status. For each context the replay changes one output field and checks the original exact grader. [Earlier compact panels](witness-training-discrimination.md) · [Runner](../benchmarks/witness_training_context.py)

The two broader selectors preserve the earlier training distinctions and add either every observed factor pair or every observed complete context. Each chooses the smallest subset of its original training block. The original development and confirmation rows remain fixed. A supplemental panel adds one fresh scoring case per declared context, for 64 cases across the three tasks. No scoring cases enter selection.

## Results

| Training policy | Examples | Serialized input bytes | Extra development misses | Extra confirmation misses | Extra stress misses, including critical |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full blocks | 192 | 37,602 | 0 | 0 | 0 |
| Earlier declared-fault cover | 80 | 16,566 | 98 | 28 | 101, including 53 critical |
| Factor-pair cover | 151 | 29,433 | 26 | 5 | 30, including 20 critical |
| Complete-context cover | 181 | 36,017 | 0 | 0 | 0 |

Each miss counts a scoring case and training-block combination for which the full block exposes the fault and the compact block does not. The factor-pair cover saved 21.7% of bytes. Its remaining misses came from higher-order warehouse contexts. Preserving complete contexts avoided those added blind spots and saved 4.2% of bytes by removing repeated ticket contexts. Across the 12 blocks, the full training itself missed 75 stress case and block combinations. The compact version could only preserve the evidence available in those blocks.

These are synthetic errors and serialized input bytes. The original live protocol keeps its full blocks. The replay leaves provider token counts and proposal quality unverified. [Exact cases, policy choices, and stress hashes](witness-training-context-results-v1.json)

A follow-up spread the full set of training examples across proposal calls to reduce blind spots at the same total input size. [Training block reassignment](witness-training-repartition.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, 39 targeted tests passed and two replays matched byte for byte. The CLI rejected a stale seal, and the prospective live plan preview reproduced byte for byte. Storage Guard measured 6.1 GiB free. The 39 MiB export and bounded publication worktree used the standing 0.2 GiB LAB exception. The replay made zero provider requests. [Coverage and disjointness tests](../tests/unit/test_witness_training_context.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_training_context
python -B -m benchmarks.witness_training_context \
  --execute 80d9df851565906d09a4a71f90b068933ee27ff6d2ebff611027d8539ed6b5b7 \
  --out NEW_REPORT.json
```
