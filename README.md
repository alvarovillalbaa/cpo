# CPO

Continuous Prompt Optimization (CPO) searches for a better prompt under a fixed evaluation budget. Each cycle uses training traces to propose edits, races candidates on validation, and qualifies the selected challenger against the incumbent on a separate holdout. The cycle preserves the incumbent when its challenger loses a matched critical case, regresses on a task family, or misses the minimum gain.

## Run

```sh
python -m pip install .
python -m unittest discover -s tests -v
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.frontier --protocol cpo-v2 --out cpo-v2.json
python -m benchmarks.grounded --fixture --out grounded-fixture.json
python -m benchmarks.grounded --replay grounded-fixture.json
python -m benchmarks.alternative_controls --out alternative-controls.json
```

The optimizer accepts evaluator and proposer callbacks. A proposer can return a `ProposalPair(rewrite=..., repair=...)` to evaluate the complete rewrite first. A finite proposal source can return `ProposalBatch(prompts, exhausted=True)` with its last batch so search can move to a different parent. Use `cpo.search` to inspect a search decision or `cpo.run_cycle` to separately qualify it. Call the next cycle with the returned prompt and a fresh qualification set. The core package does not require a provider SDK. See the benchmark for complete callback examples.

Typed evaluators can set `Row.fields` and supply `Observation.matched_fields` with `field_credit=True`. This lets search retain a partial repair when exact validation outcomes tie. Holdout promotion still uses exact paired passes and critical cases.

If a rewrite and repair have already been generated, pass them as `opening_pair=ProposalPair(rewrite=..., repair=...)` to `cpo.search` or `cpo.run_cycle`. The pair uses the first search round and skips the training probes and proposer call for that round. Candidates go through the same validation and, in `run_cycle`, separate holdout qualification. Count external proposal generation separately when comparing costs.

For an existing candidate pool, `cpo.select_pool` races exact validation scores within a lookup cap. It can rank challengers on a shared prefix and limit how many receive a full challenge. A candidate replaces the incumbent only after all validation rows are accounted for and the incumbent’s critical passes are preserved. [Fixed-pool benchmark](docs/fixed-pool.md)

`cpo.select_certified_pool` offers an opt-in early stop. It returns a challenger once its observed passes exceed the incumbent’s full validation score and every protected critical case passes. Its result reports score bounds. Recorded-data comparisons were mixed. [Certificate and results](docs/certified-pool.md)

## Evidence

The original deterministic benchmark reproduced the adaptive frontier’s 720 of 720 holdout passes with 692 search calls, compared with 622 passes and 1,193 calls for batched GEPA. On the separate transfer benchmark, CPO reached 814 of 864 with 974 calls, while batched GEPA reached 836 with 1,210 calls. CPO failed the transfer gate because it lost matched critical cases. The recorded unrestricted live trials also missed their improvement gates. Fresh typed provider quality remains open. [Protocol](docs/benchmark.md) · [Versioned result](docs/benchmark-results-v1.json)

The rewrite-first follow-up cleared the synthetic gate on 24 fresh trials. It passed 864 of 864 holdout cases with 892 search calls. Sequential GEPA passed 526 with 1,393 calls, and batched GEPA passed 785 with 1,231 calls. Rewrite-first lost no matched critical cases against either GEPA variant. The original CPO ordering passed 859 with 942 calls on those same rows. [Confirmation result](docs/benchmark-results-v2.json)

In a fixed-graph replay of recorded model replies, CPO cleared the gate against both GEPA controls on the second trial. Stopping at known proposal exhaustion saved 254 of 1,399 calls on matched splits and preserved all selected prompts. The replay isolates selection and leaves fresh model-backed performance unverified. [Recorded replay](docs/recorded-replay.md)

The first live typed study failed its development gate. CPO 0.2.0 passed 0 of 108 holdout replies, and each GEPA control passed 1 of 108. The run reproduced offline. CPO 0.3.0’s optional field-aware search has a separate recorded-replay result. The grounded fixture exercises the full comparison locally with scripted replies. [Live results](docs/model-backed-validation.md#first-live-result) · [Grounded fixture](docs/model-backed-validation.md#portable-grounded-fixture)

CPO draws on reflective feedback and complementary candidates from GEPA, attempt history from OPRO, and the separation of proposal generation and validation from MIPROv2. Its guarded promotion rule and comparison suite make these choices measurable. [GEPA](https://arxiv.org/abs/2507.19457) · [OPRO](https://arxiv.org/abs/2309.03409) · [MIPROv2](https://arxiv.org/abs/2406.11695)

The alternative-controls fixture adds demonstrations to CPO and field-aware GEPA. CPO matched GEPA's 162 of 162 exact passes and spent 288 search calls against GEPA's 298, below the 10% savings gate. The same fixture compares scored instruction history and a fixed grid of instruction and demonstration combinations. [Protocol and results](docs/alternative-controls.md)

In a six-seed follow-up, the precomputed opening with two examples per later reflection cleared the fixture gate against field-aware GEPA under both scripted proposers. When the proposer required an observed error before repairing a field, CPO passed 324 of 324 holdout cases using 567 search calls. GEPA passed 314 using 641. One-example feedback lost matched critical cases at the tighter cap. Live performance remains unverified. [Feedback budget study](docs/feedback-budget.md)
