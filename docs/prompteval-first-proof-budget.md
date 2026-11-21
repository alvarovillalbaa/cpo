# Rotating validation witnesses in the PromptEval replay

Rotating the validation case order each cycle and comparing two eligible challengers produced 25,986 held-out passes at 52,683 paid lookups. Batched GEPA at its cheaper tested setting produced 25,980 passes at 67,782 lookups. The CPO variant saved 22.3% of the lookups and was cheaper on all 20 panels. At its wider setting, batched GEPA scored 88 more passes than the CPO variant. [Full results](prompteval-first-proof-budget-results-v1.json)

The replay uses the same 20 public PromptEval model and subject panels and 640 four-cycle episodes as the previous comparison. All arms use the same supplied roster of 12 candidates per cycle, 24 shared validation anchors, case-level search cache, and independent paired qualification with the retire-assigned rule. Paid lookups count distinct search observations within an episode and the grades actually read during qualification. The runner verifies the previous plan and receipt hashes and reproduces released CPO's per-panel totals at the two shared ceilings. The table takes native GEPA results from that verified receipt. [Reference replay](prompteval-qualification-case-reuse.md)

The primary arm ranks the first two proposals on training cases and nominates the first challenger with a strict validation certificate. At cap 72, it tied released CPO at the same cap and spent 1,349 more lookups. At cap 88, accepting the first proof without training ranking saved 25,241 lookups and lost 41 passes compared with released CPO. At cap 136, the strongest CPO variant in this replay still trailed batched GEPA by 20 passes and used 112,154 more lookups. [Benchmark runner](../benchmarks/prompteval_first_proof_budget.py)

The exploratory witness arms use only the validation split to nominate. They scan the incumbent's case order for the first pass and first miss. An eligible challenger fixes the miss and preserves the sampled pass when one is found. The two-finalist variant compares up to two eligible challengers on one other validation row when the budget permits. Proposal order breaks ties. Rotation shuffles the same validation cases with the cycle's fixed seed. The witnesses screen candidates for independent qualification, which decides whether to promote them. For each witness variant, all tested caps from 56 through 136 yielded the same totals.

| Method | Per-cycle search cap | Held-out passes | Paid lookups |
| --- | ---: | ---: | ---: |
| CPO, fixed witness | 56 | 25,899 | 40,482 |
| CPO, fixed witness with two finalists | 56 | 25,904 | 44,634 |
| CPO, rotating witness | 56 | 25,975 | 47,473 |
| CPO, rotating witness with two finalists | 56 | 25,986 | 52,683 |
| Batched GEPA | 88 | 25,980 | 67,782 |
| Released CPO | 72 | 26,000 | 123,413 |
| CPO, training-ranked opening, primary arm | 72 | 26,000 | 124,762 |
| Sequential GEPA | 88 | 26,023 | 124,361 |
| CPO, first proof | 88 | 26,001 | 147,573 |
| Released CPO | 88 | 26,042 | 172,814 |
| Batched GEPA | 136 | 26,074 | 153,136 |
| CPO, screen then prove | 136 | 26,054 | 265,290 |
| Released CPO | 136 | 26,043 | 296,981 |

Against batched GEPA at cap 88, the rotating two-finalist arm improved nine panels, tied one, and regressed on ten. Its pass deltas were −19 in development, −2 in retrospective transfer, and +27 in the episode-budget subjects. Dropping one subject at a time moved the pooled delta from −34 to +25. Professional accounting contributed +40 on its own. The witness arms were developed after examining these same cohorts, and archive cases recur across seeds. An independent quality gain and the cost of live proposal generation remain unmeasured.

## Reproduce

Use Python 3.12, the hash-pinned GEPA 0.1.4 wheel, and a fresh output path. The final seal adds the exploratory witness arms while preserving the primary arm and previous trace digests. Verification used a disposable source and wheel overlay bounded at 0.2 GiB under the standing LAB storage exception. Storage Guard measured 9.3 GiB free. All replay reads used local correctness matrices with DNS and outbound sockets blocked. [Benchmark wheel](../requirements-benchmark.txt) · [Tests](../tests/unit/test_prompteval_first_proof_budget.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_first_proof_budget
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_first_proof_budget \
  --execute 2a06ab1d3942d4e47deab604a2ad7a2f4461d92dbc2c5a4338770f03b6bdb1d5 \
  --out NEW_REPORT.json
```

The receipt SHA-256 is `2d507b5b2715ffe0a44dde9c8bb7e9194291ef229a9589ca554a7d984e370f31`.
