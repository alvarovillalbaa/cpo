# Rehearse CPO and GEPA with independently drafted prompts

The archived comparisons supplied the same proposals to each optimizer. This fixture rehearses a comparison where first-gain CPO, exact-nominee CPO, successive halving, and native sequential and batched GEPA draft separately. Each arm runs three cycles on the same ticket, warehouse, and outage tasks. [Archived first-gain evidence](certified-strict-gain-transfer.md) · [Sealed plan](first-gain-independent-proposals-plan-v1.json) · [Runner](../benchmarks/first_gain_independent_proposals.py)

At each cycle, every arm gets the same 16 labeled training cases, six validation cases, and four independent qualification cases. It can make up to two reflection requests for one proposal each. CPO and halving draft a rewrite and repair from the incumbent after two training lookups, with up to 21 evaluation lookups per cycle including those probes. Native GEPA chooses its own parents and training minibatches with up to 32 evaluation lookups per cycle. Each CPO call executes one cycle and chooses its opening from the last qualified incumbent's grades.

The journal charges each arm for its own reflection. It can share a reply when the task, role, prompt, input, and repeat are identical. Each distinct final prompt and the initial prompt receive every paired holdout case and repeat. The frozen gate checks score floors, critical cases, gain, and efficiency against all four controls using both search tallies. [Packaged first-gain API](first-gain-episode.md)

| Request role | Ceiling | Physical fixture requests |
| --- | ---: | ---: |
| Reflection | 90 | 82 |
| Training and validation evaluation | 1,143 | 609 |
| Independent qualification | 360 | 261 |
| Paired holdout | 648 | 648 |
| **Total** | **2,241** | **1,600** |

The fixture forced an outage nomination rejection in every arm and verified that each next cycle kept the preceding incumbent. In warehouse, sequential GEPA used its first draft as the parent for a second reflection in the same cycle. All five final prompts tied on scripted grades. First-gain CPO also tied exact nomination on search uses, so it failed the gain-or-efficiency rule against that control. These scripted outcomes verify the accounting and decision paths. Fresh proposals and real model quality and cost remain unverified. [Verification receipt](first-gain-independent-proposals-rehearsal-v1.json)

A later audit found mismatched training feedback in nine batched GEPA reflections. The corrected portable fixture binds each reflection to its own sampled training cases. [Correction and reproduction command](first-gain-native-feedback.md)

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Running without arguments previews the plan and seal.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.first_gain_independent_proposals \
  --fixture 4e622cefedca4a2a00e2396d6c6f20dfab849be8943ddf8ad03b507551e61282 \
  --out NEW_FIXTURE
python -B -m benchmarks.first_gain_independent_proposals \
  --replay NEW_FIXTURE --out NEW_REPLAY
```

Two fixture runs and the replay produced four byte-identical archive files. All 21 focused tests passed. The tests cover the second native reflection, rejection and incumbent carryover, rejection of holdout feedback in a reflection, stale seals, and model-delivered archives. In the final verification, sockets and DNS were blocked and zero provider requests were sent. Storage Guard measured 8.5 GiB free. The bounded workspace occupied 130 MiB under the standing LAB exception. [Tests](../tests/unit/test_first_gain_independent_proposals.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
