# Recover a usable opening when a proposal hits its output cap

The GPT‑6 Luna v5 journal recorded 1,200 reasoning tokens and no returned instructions on the shared outage opening. The two preceding tasks completed search. The eight completed single-instruction reflections on those tasks used 164 to 653 output tokens. The outage opening supplied no observation of a single-instruction fallback. [Live development summary](model-backed-validation.md#live-run-with-a-precomputed-opening)

`cpo.opening.collect_opening` accepts a caller-supplied request callback and supports a joint pair, two separate requests, or a joint request followed by requests for missing slots. It preserves valid instructions in rewrite-first order and records the cap, completion status, and accepted slots for each attempt. A caller can pass the resulting prompts to its search as a `ProposalBatch`. An empty result lets it start with the ordinary proposer. [Package API](../cpo/opening.py)

Only completed replies can supply instructions. The parser checks uniqueness, the JSON shape, and serialized instruction length. An explicitly capped reply can leave a slot empty. Callback exceptions propagate before another attempt. The helper reserves each attempt's full output cap before calling the responder. Callers own transport, input-token quotas, and durable request accounting.

## Scripted comparison

The fixture gives every optimizer the same available opening instructions and charges each shared attempt to every arm. It meters all physical calls. Each opening call has a 1,200-token cap. Filling both missing slots reserves up to 3,600 output tokens across three requests. The fixture injects known cap failures and returns the same rule templates when the respective requests complete.

| Outage opening profile | Joint pair | Separate requests | Fill missing slots |
| --- | ---: | ---: | ---: |
| Complete | 414 | 417 | 414 |
| Joint pair capped | Aborted at 265 | 417 | 416 |
| Joint pair and repair capped | Aborted at 265 | 424 | 423 |
| All opening requests capped | Aborted at 265 | 443 | 442 |

The table counts physical search calls across three tasks. The clean pair reproduced the original fixture selections, search cost, and qualification. All eight split or recovery runs completed qualification. CPO passed 108 of 108 scripted qualification replies in each. With no opening, it used ordinary reflections. Live model behavior at these caps and the outcome of the sealed Luna recovery remain unverified. [Results and journal hashes](opening-budget-results-v1.json)

## Reproduce

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_budget
PYTHONHASHSEED=0 python -B -m benchmarks.opening_budget \
  --execute 1a07a7c6b2a380947eca057cca5491a07aa57e6ca18d6ea95f1e5fec69f5bba7 \
  --out NEW_REPORT.json
```

With pinned GEPA 0.1.4, two offline source-export runs matched byte for byte with sockets and DNS blocked. Seven focused tests passed. The CLI rejected a wrong seal and refused an existing output path. Storage Guard measured 20.9 GiB free. The 15.5 MB temporary source and dependency overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_opening.py)
