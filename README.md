# CPO

Continuous Prompt Optimization (CPO) searches for a better prompt under a fixed evaluation budget. Each cycle uses training traces to propose edits, races candidates on validation, and qualifies the selected challenger against the incumbent on a separate holdout. The cycle preserves the incumbent when its challenger loses a matched critical case or misses the minimum gain.

## Run

```sh
python -m pip install .
python -m unittest discover -s tests -v
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.frontier --protocol cpo-v1 --out cpo-v1.json
```

The optimizer accepts evaluator and proposer callbacks. Use `cpo.search` to inspect an optimizer decision or `cpo.run_cycle` to separately qualify it. Call the next cycle with the returned prompt and a fresh qualification set. The core package does not require a provider SDK. See the benchmark for complete callback examples.

## Evidence

The original deterministic benchmark reproduced the adaptive frontier’s 720 of 720 holdout passes with 692 search calls, compared with 622 passes and 1,193 calls for batched GEPA. On the separate transfer benchmark, CPO reached 814 of 864 with 974 calls, while batched GEPA reached 836 with 1,210 calls. CPO failed the transfer gate because it lost matched critical cases. The recorded unrestricted live trials also missed their improvement gates. Fresh typed provider quality remains open. [Protocol](docs/benchmark.md) · [Versioned result](docs/benchmark-results-v1.json)

CPO draws on reflective feedback and complementary candidates from GEPA, attempt history from OPRO, and the separation of proposal generation and validation from MIPROv2. Its guarded promotion rule and comparison suite make these choices measurable. [GEPA](https://arxiv.org/abs/2507.19457) · [OPRO](https://arxiv.org/abs/2309.03409) · [MIPROv2](https://arxiv.org/abs/2406.11695)
