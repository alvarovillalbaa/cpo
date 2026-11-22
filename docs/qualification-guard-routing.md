# Choose a qualification guard from paid validation

The cap-19 deferred screen certifies a validation nominee before independent qualification. This replay chooses the qualification proof from the paid incumbent and nominee validation replies. It keeps the original precheck, search, nominee, cases, and lookup cap. [Deferred screen](deferred-certificate-cycle.md) · [Regression-free qualification](regression-free-qualification.md)

- **After an observed regression.** Use the regression-free proof if the paid nominee grade fails a case the incumbent passed.
- **Unless preservation is proved.** Use the regression-free proof if any incumbent pass lacks a paid nominee pass. That includes observed failures and unread nominee grades.

The replay covers 4,288 schedules on 134 archived model panels. It checks that both routes use the exact callback path of their chosen fixed proof on every schedule. Across 1,398 nominees, validation proved preservation for 952, observed a regression for 77, and left preservation unverified for 369. The gate requires spending at most the cheaper fixed policy’s lookup count and a nonnegative lower paired endpoint against both fixed policies. [Strata, paired ranges, and exact budget bounds](deferred-certificate-guard-routing-results-v1.json)

## Results

Each cell gives the pass and lookup differences relative to ordinary one-gain qualification. A negative lookup difference means the route saved lookups.

| Cohort | Guard after observed regression, pass / lookup change | Guard unless preservation proved, pass / lookup change |
| --- | ---: | ---: |
| BBH, original | −30 / −21 | −18 / −79 |
| BBH, other checkpoints on previously studied tasks | −3 / −9 | −6 / −39 |
| BBH, causal judgment | 0 / 0 | 0 / −3 |
| LMentry, original | 0 / −14 | −9 / −61 |
| LMentry, other checkpoints on previously studied tasks | +11 / −18 | −15 / −55 |
| LMentry, ends-with-word | 0 / 0 | 0 / −5 |
| Disjoint MMLU | 0 / +2 | 0 / +3 |
| Earlier MMLU | 0 / −5 | 0 / −17 |

The only gate pass was guarding unless preservation was proved on BBH causal judgment. It saved three lookups against ordinary one gain and two against the always-on guard with the same deployments. On LMentry with other checkpoints, the observed-regression route added 11 passes versus ordinary one gain with a paired range of +2 to +20. It still used 60 more lookups than the always-on guard.

Both routes missed the 11 passes recovered by the always-on guard on disjoint MMLU. All three deployment changes that produced those passes occurred after paid validation had already proved preservation. The results leave both routes experimental and fresh-model performance unverified.

## Reproduce

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_certificate_guard_routing
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_certificate_guard_routing \
  --execute 88903d1750f083d5126d66f903d8e38c7c00e02d60c3fa4bae59867b9c410b53 \
  --out NEW_REPORT.json
```

The two clean-source runs matched byte for byte at SHA-256 `8feb37f566d6c8dfdd5881e2e889b5244c076fd5f75f54ee596ec248ca6e0508`. They verified 8,576 routed paths. DNS and outbound sockets were blocked, and the CLI rejected the predecessor seal before writing an output. [Replay driver](../benchmarks/deferred_certificate_guard_routing.py) · [Route tests](../tests/unit/test_deferred_certificate_guard_routing.py)
