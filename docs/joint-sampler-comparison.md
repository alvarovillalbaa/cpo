# Combine model-based joint sampling with exact CPO bounds

Each task uses a fixed pool of instructions crossed with four demonstration settings. The instructions come from the starting prompt, two scripted opening proposals, and one scripted repair update. The demonstration settings are empty or one of three disjoint four-case bundles drawn from training. Every optimizer gets the same pool and is charged the same two shared proposal calls. Six task seeds cover tickets, warehouse release, and outage credits. Validation selects one challenger. Eight disjoint cases qualify it before final scoring on 18 holdout cases. [Fixture and earlier comparison](alternative-controls.md) · [Runner](../benchmarks/joint_sampler_comparison.py)

CPO uses its exact fixed-pool race with a one-case screen. Full grid reads complete scores in the same seeded candidate order. Both official GEPA 0.1.4 modes may also spend their search allowance on training. For the model-based control, official Optuna 4.5.0 uses a multivariate TPE sampler on the instruction and demonstration indices. Random sampling follows the same trial, confirmation, and budget schedule. This comparison isolates candidate allocation from the bootstrapping and model-based proposal stages of MIPROv2. [DSPy implementation](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/mipro_optimizer_v2.py) · [Optuna TPE](https://optuna.readthedocs.io/en/v4.5.0/reference/samplers/generated/optuna.samplers.TPESampler.html)

Both samplers score the same three-case validation prefix, with exact passes weighted above partial fields. Every third trial, and once at the end, the best unconfirmed affordable candidate can earn a complete check. **TPE with CPO bounds** preserves that policy and can abandon a candidate once its best possible exact score cannot improve or a protected validation case fails. A promoted validation nominee still needs a complete exact score. Paid lookup totals include search, qualification, and the two shared proposal calls.

## Results

Each cell shows holdout passes out of 324 / paid lookups.

| Method | Cap 48 | Cap 72 |
| --- | ---: | ---: |
| CPO | 274 / 1,003 | 311 / 1,109 |
| Full grid | 292 / 966 | 302 / 1,110 |
| Random sampler | 240 / 985 | 312 / 1,216 |
| Optuna TPE | 309 / 960 | 311 / 1,095 |
| TPE with CPO bounds | 309 / 954 | 311 / 1,064 |
| Batched GEPA | 272 / 885 | 302 / 1,022 |
| Sequential GEPA | 272 / 849 | 300 / 1,022 |

The hybrid chose identical final programs to plain TPE on all 36 panels across both caps. It saved six lookups at cap 48 and 31 at cap 72. At cap 72, it used the headroom for 13 additional sampler trials and three additional confirmations. Compared with CPO alone, the hybrid gained 35 passes and saved 49 lookups at cap 48 while losing four matched critical passes. It matched CPO’s score and saved 45 lookups at cap 72 with no matched critical losses. Both GEPA modes spent fewer lookups at both caps, and the hybrid lost matched critical passes against both at cap 72. [Full paired outcomes and costs](joint-sampler-comparison-results-v1.json)

The fixture supports combining model-based search with exact rejection on a fixed set of instruction and demonstration choices. Fresh proposal quality and end-to-end MIPROv2 performance remain unverified.

## Reproduce

Use GEPA 0.1.4 and Optuna 4.5.0 in an isolated benchmark environment. The receipt records wheel fingerprints and the existing Python dependency versions used for the replay.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.joint_sampler_comparison
PYTHONHASHSEED=0 python -B -m benchmarks.joint_sampler_comparison \
  --execute 0c6021ebb6adf4f20a5fb8a39f2d24fb8ab5eb44e768218c70e394872dc118b9 \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked. Six focused tests passed, including exhaustive checks of bounded confirmation with prepaid evidence. The six original arms reproduced their provisional selections, scores, and costs after adding the hybrid. The CLI rejected a wrong seal and declined to overwrite an existing report. Storage Guard measured 20.4 GiB free. The 27.5 MB temporary source and wheel overlay was removed under the standing LAB exception. [Verification receipt](joint-sampler-verification-v1.json) · [Focused tests](../tests/unit/test_joint_sampler_comparison.py)
