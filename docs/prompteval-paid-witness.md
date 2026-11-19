# Choose the first-gain case using paid search history

A first-gain screen can spend its whole proposal scan on a case that none of the challengers passes. This experiment tests whether outcomes paid for in earlier cycles can identify a better case to probe. It compares two policies with the original first-gain rule. [Original screen](single-finalist.md)

- **Avoid two failures** keeps the seeded order, except that it places misses with at least two prior failures by other prompts and zero prior passes after other misses.
- **Smoothed pass rate** chooses the missed case with the highest smoothed fraction of prior passes. It adds one pass and one failure to each count and keeps the seeded order on ties.

Each episode starts with empty history. History uses distinct prompt and case pairs paid for during prior validation searches in the same episode, excludes the current incumbent from the witness statistics, and omits qualification and holdout outcomes. Witness selection itself uses no additional evaluations. A different witness can change the number of evaluations the ensuing certificate or qualification spends.

The plan fixes both policies before replay across 18 archived PromptEval panels. Six panels reproduce the previous first-gain trace. Four development panels and eight retrospective-transfer panels reuse the earlier validation-size study and its matched GEPA totals. Each episode has four cycles, a 12-case validation panel, a search cap of 52, and eight independent qualification cases per cycle. The runner compares full sequential and batched GEPA control traces across policies. [Validation size study](prompteval-validation-size.md) · [Benchmark runner](../benchmarks/prompteval_paid_witness.py)

## Results

Each cell reports final holdout passes and paid lookups. The last column counts panels meeting both GEPA gates across all three cohorts.

| Policy | Development | Finalist transfer | Retrospective transfer | Both GEPA gates |
| --- | ---: | ---: | ---: | ---: |
| First-gain | 4,149 / 14,775 | 4,455 / 21,833 | 10,187 / 29,873 | 4 / 18 |
| Avoid two failures | 4,149 / 14,794 | 4,455 / 22,064 | 10,193 / 29,894 | 4 / 18 |
| Smoothed pass rate | 4,146 / 14,958 | 4,465 / 22,135 | 10,197 / 30,037 | 3 / 18 |
| Sequential GEPA | 4,128 / 21,574 | 4,483 / 31,157 | 10,219 / 43,164 | — |
| Batched GEPA | 4,150 / 15,311 | 4,466 / 22,028 | 10,244 / 30,632 | — |

The primary rule changed the witness in 77 cycles, gained six aggregate passes, and added 271 lookups. It exchanged one qualifying panel with first-gain. The smoothed rule changed the witness in 245 cycles, gained 17 passes, and added 649 lookups. It improved five panels and lost passes on six, with business ethics contributing 12 of its 17 aggregate gains. It finished 22 passes behind sequential GEPA and 52 behind batched GEPA in aggregate.

The gate requires at least as many passes at equal or lower cost against each control, with 10% savings required on a pass tie. Replays reuse holdout cases across the 32 episodes per panel. The results describe archived prompt selection, so both witness policies stay in the benchmark. Each phase reproduced byte for byte in two offline executions. [Sealed results](prompteval-paid-witness-results-v1.json)

A reachability audit found that an optimistic path through both strict gates could match the GEPA score in 153 of 166 losses using fresh prompts alone. Allowing validation ties explained two further losses after granting broad archive access. [Gate reachability audit](prompteval-gate-reachability.md)

## Reproduce

Use pinned GEPA 0.1.4. Preview each phase to obtain its seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_paid_witness --phase finalist-transfer
```

The other phases are `development` and `retrospective-transfer`.
