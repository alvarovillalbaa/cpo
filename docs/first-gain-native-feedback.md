# Send GEPA the training feedback it sampled

The original independent-proposal fixture built the native GEPA reflection payload from the parent's most recently paid training replies. Native GEPA 0.1.4 supplies the selected minibatch to its custom proposer. In the width-two run, GEPA evaluates both parent minibatches before calling either proposer. The original adapter supplied the second minibatch's feedback to both reflections. The instrumented replay reproduced all four original fixture files byte for byte and compared the paid payload with GEPA's selected training trajectories. [Original study](first-gain-independent-proposals.md) · [Audit and corrected fixture](../benchmarks/first_gain_native_feedback.py)

| Native control | Reflections | Different training cases in the original payload |
| --- | ---: | ---: |
| Sequential GEPA | 10 | 0 |
| Batched GEPA | 18 | 9 |

The corrected adapter passes each paid training observation to native GEPA as evaluator side information. Each reflection receives its own selected parent and sampled observations in the order GEPA supplies them, including cached observations. Validation and qualification evidence stay outside reflection. The adapter preserves the original disjoint loaders, all labeled training inputs, scoring, and request caps. The original protocol and fixture remain available under their existing seals. [Sealed correction and case IDs](first-gain-native-feedback-v1.json)

The corrected scripted run used 82 reflections, 609 evaluations, 261 admission lookups, and 648 holdout lookups. Apart from the new plan identity, the run changed only the nine native reflection payloads. The scripted drafts, deployments, scores, costs, and failed development gate reproduced. The fixture uses scripted drafts, so it leaves the effect of the corrected feedback on fresh prompts unmeasured. The existing Luna development seal still references the original portable protocol. It needs a separate SDK binding to run the corrected comparison.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Run without arguments to preview the corrected plan.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_native_feedback \
  --fixture a9b86594843dfe2b0f71685858fc13821148c2f672767a41c1711a6d58da89ee \
  --out NEW_REPORT.json
```

Two network-blocked runs produced identical reports at SHA-256 `3da4f61194d428ecae131ae1c6df768593de46ce1a448b72108eae31f9e9b2a2`. All 18 focused tests passed, including the actual native minibatch regression, the independent-proposal fixture, and the original confirmation binding. The runner refused stale seals and occupied output paths. Storage Guard measured 7.6 GiB free. The isolated source export, wheel overlay, and publication checkout fit within 0.16 GiB under the standing LAB exception. Zero provider requests were sent. [Regression test](../tests/unit/test_first_gain_native_feedback.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
