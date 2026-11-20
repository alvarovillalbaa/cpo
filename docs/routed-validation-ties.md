# Give a witnessed validation tie an independent qualification

On the Llama and Mistral confirmation panels, sequential GEPA at cap 52 won 79 of 512 paired episodes. Its final prompt had a nonpositive validation gain against CPO's incumbent in 27 of those episodes, accounting for 58 of the 172 gross lost passes. Another 15 losing episodes involved a prompt with a strict gain on both archived panels that the CPO screen missed. These labels compare the realized paths after selection. [Frozen confirmation](routed-start-model-confirmation.md)

## Selection and qualification

Strict search keeps priority. When it keeps the incumbent, the new rule inspects its paid validation journal. A tie candidate must have passed a measured incumbent miss and have an upper score bound exactly equal to the fully measured incumbent score. It must preserve the incumbent's critical passes. The rule can nominate an already certified tie or spend up to two or four additional search lookups per cycle to finish one. The remaining original search budget also bounds the extension. A failed reply ends a tie proof because every remaining response was needed to tie.

Each successful tie has to earn qualification on the reserved independent cases. The stronger variants require two net gains or nonnegative gain in both qualification halves plus a positive total. A rejected tie is excluded from future archive nominations. A strict candidate goes through the original route and qualification. All arms share the original proposal blocks, cases, search ceiling, and final holdout. [Search and replay implementation](../benchmarks/routed_validation_ties.py)

## Results

Each cell shows holdout passes / distinct paid search and qualification lookups.

| Policy | BBH and LMentry | MMLU pilot | Earlier MMLU model transfer | Llama and Mistral confirmation |
| --- | ---: | ---: | ---: | ---: |
| Strict validation | 3,381 / 48,415 | 22,351 / 33,554 | 12,225 / 52,028 | 17,724 / 49,330 |
| Already-paid tie | 3,411 / 49,565 | 22,351 / 33,789 | 12,231 / 52,549 | 17,722 / 49,749 |
| Finish with at most two reads | 3,422 / 50,356 | 22,348 / 34,090 | 12,234 / 53,372 | 17,726 / 50,268 |
| Finish with at most four reads | 3,422 / 50,567 | 22,347 / 34,300 | 12,232 / 54,035 | 17,733 / 50,644 |
| Four reads, two qualification gains | 3,410 / 50,192 | 22,351 / 34,150 | 12,225 / 53,896 | 17,725 / 50,522 |
| Four reads, split qualification | 3,409 / 50,434 | 22,347 / 34,300 | 12,232 / 54,015 | 17,733 / 50,622 |
| Batched GEPA, cap 52 | 3,396 / 47,537 | 22,352 / 38,990 | 12,181 / 57,817 | 17,694 / 57,271 |
| Sequential GEPA, cap 52 | 3,457 / 65,252 | 22,361 / 56,504 | 12,253 / 83,250 | 17,721 / 81,537 |

On the confirmation panels, finishing a tie with up to four reads nominated 85 ties and promoted 21. It gained **nine passes** over strict CPO and spent **1,314 additional lookups**. The 171 extra search probes account for part of that increase. The rest comes from new qualification and the changed search trajectories. The central 95% paired range against strict CPO was −8 to +26 passes. Nine episodes improved and five regressed. [Per-panel totals and decision receipts](routed-validation-ties-results-v1.json)

Requiring two net qualification gains cut tie promotions to two on the confirmation panels and cut the gain over strict CPO to one pass. Split qualification matched the ordinary four-read score and saved 22 lookups there, with 13 fewer passes on BBH and LMentry. The ordinary four-read policy lost four passes against strict CPO on the MMLU pilot. On confirmation, it led sequential GEPA by 12 passes and batched GEPA by 39, with 37.9% and 11.6% fewer lookups, respectively. Its joint paired range against those cap-52 controls was **−50 to +70 passes**. The four-read policy was selected for this retrospective range after comparing variants on the same archived outcomes. Fresh proposal quality and provider costs remain unverified.

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Preview each phase to get its seal. The other phases are `model-transfer`, `bbh-lmentry`, and `mmlu`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.routed_validation_ties --phase confirmation
PYTHONHASHSEED=0 python -B -m benchmarks.routed_validation_ties \
  --phase confirmation --execute 9da27b5f0b4257648294ff34efe04bf586257c16fd52e6d3bef225c282958643 \
  --out NEW_REPORT.json
```

Two source-export replays per cohort matched byte for byte with sockets and DNS blocked. The strict arm reproduced all 56 published CPO panel traces, and the loss audit reproduced 48 GEPA panel traces. Two focused tests exercised 1,536 binary outcome and journal combinations and checked critical-case protection and an exhausted search budget. The CLI rejected an incorrect seal. Storage Guard measured 14.9 GiB free. The 15.1 MB scratch overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_routed_validation_ties.py)
