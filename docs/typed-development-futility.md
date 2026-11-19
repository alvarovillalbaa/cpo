# Early rejection of a typed development trial

The completed GPT-6 Luna v1 development trial sent 216 qualification requests for 540 logical arm replies. Replaying its original request order, the tenth provider reply made qualification impossible. The ticket task required 27 passes and could reach at most 26 even if every remaining ticket reply for CPO passed. The replay would have skipped 206 qualification requests. Recorded token usage for that suffix is $0.274521 at the sealed plan rates. [Completed trial](model-backed-validation.md#first-live-result) · [Result and source fingerprints](typed-development-futility-results-v1.json)

The check keeps one result per physical request, including all arms sharing that request. For an unseen sample, every arm attached to that sample gets the same hypothetical result. An unseen sample shared with CPO passes in the optimistic completion. Other unseen samples fail. This simultaneously maximizes CPO's own task totals and every paired margin. When arms share a sample, its outcome cancels in their comparison. This completion gives CPO its best chance to clear the task floors, preserve the initial and GEPA scores, avoid critical losses, and meet each comparator's quality or efficiency gate. If it fails, no completion of the same schedule can qualify.

The replay checks rejection only. A future trial using the rule could stop sending qualification requests after a definitive rejection. Scores for omitted replies would be unknown. The v1 run actually sent all 216 qualification requests, and the sealed v5 recovery has its original protocol. Fresh model quality and any savings in a future run remain unmeasured.

## Reproduce offline

Use the `qualification` subdirectory of the original `live-cpo-luna-typed-v1` archive. The verifier checks the source hashes, aligns response IDs and shared arm grades, and reconciles token usage at the original rates.

```sh
python -B -m benchmarks.typed_development_futility \
  --archive PATH_TO_LIVE_CPO_V1/qualification --out NEW_REPORT.json
```

Two runs produced byte-identical reports. Tests compared the optimistic test with every possible completion of a small matched panel across multiple task floors, required gains, and search costs. The historical trial also reproduced separately with its pinned CPO and GEPA versions. [Verifier](../benchmarks/typed_development_futility.py) · [Completion tests](../tests/test_typed_development_futility.py)
