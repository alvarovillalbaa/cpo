# Offline reconstruction of the outage holdout requests

The independent audit found two outage finalists without replies on the original 18-case holdout. This packet reconstructs those 36 missing request bodies and all 72 bodies needed to measure the four finalists together. The original prompt text and case inputs stay in the source archives. The packet records identifiers and hashes. [Independent holdout audit](recorded-independent-holdout.md)

## What was verified

The capture uses the archived runner’s candidate call with the local OpenAI Agents SDK adapter. It intercepts serialization at the adapter’s transport and returns a local failure before provider dispatch. Each captured body uses the historical `gpt-6.2-sol` alias, low reasoning effort, a 384-token output limit, and `store=false`. The packet binds the source archive, runtime, lockfile, installed SDK versions, and executable by hash.

All 90 original outage reservation amounts agreed with the amounts calculated from the reconstructed SDK body lengths. The source journals contain neither historical request-body hashes nor a pinned provider model snapshot. The length check corroborates the request reconstruction. The new SHA-256 values fingerprint the bodies emitted by the verified local SDK. [Capture receipt](recorded-holdout-request-packet-v1.json)

The 36 missing outcomes remain unobserved. A new comparison can measure all four finalists together under one verified model configuration using the 72-slot layout. Combining new estimates with the old replies would require evidence of a common model snapshot and compatible request settings. Use the [offline journal scorer](recorded-holdout-score.md) to check and compare replies for this packet once they exist.

## Reproduce the offline packet

Run the preview from CPO with the verified source archive and the installed runtime dependencies. Add `--execute PLAN_SHA256 --out NEW_FILE` to capture the packet into a fresh file. The command invokes a local stub with real network routes disabled.

```sh
node benchmarks/recorded_holdout_requests.mjs \
  --audit FULL_INDEPENDENT_HOLDOUT_AUDIT.json \
  --archive ORIGINAL_OPEN_EVALS_STUDY \
  --source-plan REWRITE_FIRST_PLAN.json \
  --runtime PATH_TO_OPENAI_RUNTIME_MODULE
```

Two captures produced byte-identical packets. A stale seal or an existing output path was rejected before capture. No inference or credential lookup is needed.
