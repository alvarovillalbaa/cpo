# Typed policy coverage beyond the sealed Luna panel

The sealed confirmation panel has 24 distinct input strings. Every case repeats a policy regime present in training. Ticket topics determine the queue regardless of channel or reference. Warehouse regimes use the sign of usable stock, inspection, tier, and site. Outage regimes use duration, plan, evidence, and whether the fee cap binds, ties, or leaves the credit unchanged. All eight original ticket topic and channel combinations also appeared before confirmation. Distinct input strings give a fresh sample on these regimes. The panel leaves performance on unobserved policy combinations unmeasured. [Audit and fixture results](quoted-luna-policy-stress-v1.json)

The separate stress fixture retains eight cases per task and the original critical-case counts of three tickets, five warehouse cases, and three outages. It uses the same answer schema and policy rules.

| Task | Stress coverage beyond the original cohorts |
| --- | --- |
| Ticket | Six mapped topics through new channel values and two unseen topics that use the default route. All eight topic and channel combinations are new. |
| Warehouse | All six previously unused combinations of stock, inspection, tier, and site, with two additional numeric cases in those combinations. |
| Outage | Eight new regimes, including an active cap at 30 minutes, a tied cap just below the long-outage threshold, and missing evidence that overrides the long-outage reason. |

The local SDK replay reproduced the sealed iterative development journal before scoring its admitted prompts on both panels. The same deterministic rule evaluator graded both panels without forcing correct answers for any arm. CPO, sequential GEPA, and batched GEPA each passed **48 of 48** replies on each panel. The starting prompt passed four. CPO's search charge stayed 13.3% below sequential GEPA and 33.6% below batched GEPA at fixture rates. The paired quality test tied on both panels. These scores establish fixture behavior for the additional cases. Live prompt behavior and efficiency on these regimes remain unmeasured.

Reproduce the regime audit and case fingerprint from the source checkout. The audit checks that every new input and case ID is distinct and verifies expected grades against the policy evaluator. [Generator and audit](../benchmarks/grounded_policy_regimes.py) · [Focused tests](../tests/unit/test_grounded_policy_regimes.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.grounded_policy_regimes
```

The stress cases have a separate fingerprint. The original development and confirmation seals retain their published datasets.

### SDK confirmation rehearsal

A separate execution plan binds the stress cases to the prompts from a replayed, qualifying development archive. The iterative fixture needed 96 distinct count-and-generation pairs for 192 matched replies and reserved $0.499988 at plan rates. The quote used each request's serialized byte length, input headroom, and output cap. The SDK rehearsal accepted every request at its ceiling and refused altered bytes before token counting. A checkpoint resumed after 17 pairs and reproduced the uninterrupted journal. The linked receipt covers fixture execution and the plan's upper bound. A model quote depends on the future development archive and inference remains paused. [Checkpoint and reservation receipt](quoted-luna-stress-confirmation-sdk-v1.json)
