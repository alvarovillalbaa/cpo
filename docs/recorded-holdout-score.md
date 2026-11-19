# Verify and score an outage holdout journal offline

The scorer checks a journal against the [72 frozen request slots](recorded-holdout-requests.md), the [independent audit](recorded-independent-holdout.md), and the original outage inputs and grader. It reads existing files and writes a report to a fresh path.

```sh
node benchmarks/recorded_holdout_score.mjs \
  --packet FULL_REQUEST_PACKET.json \
  --audit FULL_INDEPENDENT_HOLDOUT_AUDIT.json \
  --cases ORIGINAL_OUTAGE_STRICT_PLAN.json \
  --grader ORIGINAL_IMPROVEMENT_PLAN.mjs \
  --wire PANEL_WIRE.jsonl \
  --out NEW_SCORE_REPORT.json
```

The four source files must match fingerprints committed with the public audit and scorer. The journal follows the packet order. Write one JSON line per record, ending each line with a newline. Each request record has a one-based `sequence`, the finalist prompt fingerprint in `arm`, `role` set to `qualification`, the exact SDK body as a string in `request`, and the recorded reservation in `reservedMicrousd`. Its next line contains the same `sequence` and the raw Responses API object in `reply`. Keep the journal with the original experiment evidence.

The report counts observed token usage from replies and records capped or refused answers as failures. A valid unfinished journal can end with an unanswered request. Its report gives the request and reply counts and omits paired comparisons. A complete journal reports pass counts, cases passed by only one finalist, and critical cases the control passed that CPO missed. The eight directions include reversals of some prompt pairs. Read them as paired comparisons on the same cases.

The report binds the supplied journal by SHA‑256. Its model label comes from the reply records. Provider provenance and the actual model snapshot require independent execution evidence. An offline fixture exercised all 72 request fingerprints, all eight comparison directions, the unanswered-request boundary, and rejection of changed requests and duplicate replies. A real panel remains pending.
