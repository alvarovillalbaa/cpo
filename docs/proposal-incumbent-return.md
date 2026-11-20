# Let the previous incumbent qualify again

The deployment-path audit found that batched GEPA accumulated its transfer lead after the two methods took different promotion paths. This replay tests whether CPO can recover by letting a displaced incumbent challenge its replacement once. [Deployment-path audit](proposal-gap-audit.md)

After a promotion, **Return** puts the just-displaced prompt into the second opening slot of the next cycle. If search nominates it, it must beat the current incumbent on fresh independent qualification cases. A prompt that fails to return expires at the end of that cycle. **Vacant** leaves the same slot empty after its own promotions. Both policies keep the original first opening, later proposals, 72-lookup search ceiling, and qualification rule. The number of reserved slots can diverge as the methods make different promotions. [Runner](../benchmarks/proposal_incumbent_return.py)

## Results

| Policy | Development passes / lookups | Transfer passes / lookups |
| --- | ---: | ---: |
| Original cap-72 CPO | 4,159 / 33,177 | 10,237 / 66,831 |
| Return | 4,159 / 33,254 | 10,239 / 66,889 |
| Vacant | 4,161 / 32,890 | 10,239 / 66,334 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 |

On the eight transfer panels, Return reserved 92 of 1,024 opening slots. It began scoring the displaced prompt in 76 cycles, completed validation in nine, nominated it in four, and restored it in two. A separate check of the archived grades found seven of the 92 displaced prompts both improved on the current incumbent’s full validation score and would have passed independent qualification. Search had access only to the replies it actually paid for.

Return and Vacant tied on total transfer passes, with gains and losses distributed differently across panels. Return used 555 more lookups than Vacant and scored two more passes than the original CPO route. It finished 24 passes behind batched GEPA and used 21,337 fewer lookups. Its paired 95% range against both GEPA controls was −76 to +25 passes. The result leaves accuracy superiority unresolved and CPO’s default remains the original search. [Panel scores, counters, and paired ranges](proposal-incumbent-return-results-v1.json)

The follow-up tested corroboration on two unused cases before accepting a one-pass promotion. [Promotion corroboration replay](proposal-qualification-corroboration.md)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_incumbent_return
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_incumbent_return \
  --execute 7e9724124e849d2d0fbbf1c30a845513afe2b9126ac6739799edc0a0a0df51e8 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each exercised 3,072 experimental cycles and reproduced 48 published panel-control traces. Eight focused tests passed, covering fresh qualification, expiry after a failed return, and the vacant-slot control. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 9.2 GiB free. The 26.5 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_incumbent_return.py) · [Verification receipt](proposal-incumbent-return-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
