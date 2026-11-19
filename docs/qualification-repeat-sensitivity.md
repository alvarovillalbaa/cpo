# Spend qualification lookups on distinct cases or repeats

In the completed GPT-6 Luna development archive, 216 physical qualification replies form 108 pairs with identical request bytes. Three pairs disagreed on exact pass or fail, all on outage credits. Nine pairs disagreed on the typed result classification and six differed in provider completion status. Most replies in that trial failed, so the observed disagreement rate only describes that run. It cannot supply a general response error rate. [Live validation record](model-backed-validation.md)

This replay compares eight distinct qualification cases, the first four cases once, and those same four cases twice. The eight-case and repeated schedules both have a ceiling of eight paired comparisons. The four-case schedule can spend up to four. All arms use the existing strict summed-gain rule for qualification. The archive attempt still debits the actual challenger reads from the fresh search allowance, so a qualification schedule can also change which candidates reach search. [Benchmark runner](../benchmarks/qualification_repeat_sensitivity.py) · [Paid-cap accounting](gepa-paid-cap-transfer.md)

## Protocol

The two cohorts include eight Gemma and Falcon panels and 12 Flan-UL2 and Mixtral panels. Each panel has 32 four-cycle episodes using the original starts, candidates and case assignments. Seeded CPO keeps its cap of 52. The original official batched GEPA 0.1.4 control uses 52 on Gemma and Falcon and 44 on Flan-UL2 and Mixtral. Each comparison uses the same qualification schedule in both optimizers. [Archived cost frontier](independent-mmlu-cost-frontier.md) · [Frozen replication settings](low-budget-transfer.md)

The simulations flip each qualification outcome with probability 0%, 1%, or 5% by a deterministic draw keyed on panel, episode, prompt, case and repeat. The same first reply is available to both optimizers and all schedules. The repeat uses its own draw. The archived correctness matrix continues to determine training, validation and final holdout. The simulated rates measure sensitivity to independent reply noise during qualification. Holdout cases recur across episodes, and the two archived cohorts were available before this replay. [Slot and noise tests](../tests/unit/test_qualification_repeat_sensitivity.py)

## Results

Each cell gives final holdout passes and distinct paid lookups across both cohorts.

| Qualification schedule | Clean replay | 1% flip probability | 5% flip probability |
| --- | ---: | ---: | ---: |
| CPO, eight distinct cases | 27,813 / 53,182 | 27,822 / 52,998 | 27,867 / 52,343 |
| CPO, four distinct cases | 27,860 / 47,450 | 27,867 / 47,273 | 27,849 / 46,726 |
| CPO, four cases twice | 27,860 / 53,018 | 27,879 / 52,803 | 27,864 / 52,279 |
| Batched GEPA, eight distinct cases | 27,862 / 59,934 | 27,870 / 59,971 | 27,868 / 59,693 |
| Batched GEPA, four distinct cases | 27,832 / 57,338 | 27,836 / 57,300 | 27,840 / 57,025 |
| Batched GEPA, four cases twice | 27,832 / 60,358 | 27,847 / 60,109 | 27,852 / 59,697 |

On clean replay, four distinct cases gained 47 passes and saved 5,732 lookups against eight-case CPO. It scored 28 more passes and saved 9,888 lookups against four-case GEPA. Against the original eight-case GEPA control, it finished two passes behind and saved 12,484 lookups. This improvement supports taking the shorter schedule into a prospective comparison with the stronger GEPA control.

Repeating the four cases at 1% noise added 12 CPO passes at a cost of 5,530 extra lookups over four single samples. At 5% it added 15 passes and 5,553 lookups. At 5%, eight distinct cases still scored higher than four repeated cases in aggregate. The two cohorts varied in which schedule scored highest. The replay leaves the qualification default unchanged. [Per-panel results and seals](qualification-repeat-sensitivity-results-v1.json)

The prospective follow-up on 12 new panels reproduced the lookup savings and found an accuracy deficit against both original GEPA modes. [Four-case qualification transfer](four-case-qualification-transfer.md)

## Reproduce

Use pinned GEPA 0.1.4. Preview each phase to get its seal, then execute with a fresh output path. The other phase is `development`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_repeat_sensitivity --phase replication
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_repeat_sensitivity \
  --phase replication --execute f1ec58483ba01f5eea80f2d92f2a9ec5ff37dfe0f81f0a827254459b9bd3ef20 \
  --out NEW_REPORT.json
```

Two runs per phase with sockets and DNS blocked matched byte for byte. The clean eight-case arms reproduced all 40 published optimizer-panel traces. The CLI rejected a stale seal before writing output. Storage Guard measured 13.6 GiB free. The standing LAB exception covered the 9.9 MB scratch overlay, which was removed. Fresh prompt quality, the effect of stochastic search replies and provider costs remain unverified.
