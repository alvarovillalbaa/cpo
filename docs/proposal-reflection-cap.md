# Limit the proposal rounds after short validation

The eight-case screen nearly matched batched GEPA on the additional archive and increased the number of calls to CPO’s proposer. This replay measures how much accuracy remains when CPO caps the calls after its precomputed opening pair. The eight-case screen, 72-lookup ceiling, complete 24-case validation of the finalist, and independent qualification follow the previous protocol. [Short-validation replay](proposal-short-validation.md) · [Runner](../benchmarks/proposal_reflection_cap.py)

The primary arm allows one later callback per cycle. Two exploratory arms allow zero or two. Every arm starts with the same supplied pair. A zero cap still allows search to score that pair. The benchmark logs CPO’s calls after the opening and instruments both official GEPA controls’ custom proposer callbacks. Replaying the instrumented controls reproduces their original lookup and deployment traces.

## Results

| Method | Development passes / lookups | Earlier transfer passes / lookups | Additional archive passes / lookups |
| --- | ---: | ---: | ---: |
| Original cap-72 CPO | 4,159 / 33,177 | 10,237 / 66,831 | 9,000 / 66,958 |
| Eight cases, zero later callbacks | 4,158 / 20,860 | 10,247 / 42,220 | 9,023 / 43,175 |
| Eight cases, up to one later callback | 4,164 / 29,130 | 10,225 / 58,768 | 9,024 / 59,701 |
| Eight cases, up to two later callbacks | 4,167 / 32,503 | 10,236 / 64,506 | 9,028 / 66,549 |
| Eight cases, original round limit | 4,165 / 32,701 | 10,252 / 65,203 | 9,019 / 66,069 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 | 9,012 / 92,773 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 | 9,020 / 89,426 |

On the additional archive, the primary arm scored four more passes than batched GEPA and used 29,725 fewer evaluation lookups. It made 1,005 later proposer callbacks across 1,024 cycles, down from 1,749 under the original eight-case round limit. The joint paired 95% range against both GEPA controls was −49 to +44 passes, so the primary arm missed the accuracy gate. It also finished 38 passes behind batched GEPA on the earlier transfer panels. CPO’s default search stays in place.

The zero-callback arm scored three passes above batched GEPA on the additional archive and 16 below on earlier transfer. Its 43,175 paid evaluation lookups on the additional archive were the lowest of the methods measured here. The arm has one supplied opening pair available per cycle. Producing that pair in a live run can incur its own cost.

The additional archive registered 12,251 sequential GEPA and 12,112 batched GEPA custom proposer callbacks. GEPA’s archived callback supplies one candidate at a time. CPO’s callback can supply two. These counts measure each adapter’s work separately, and the benchmark supplies the proposals from the archive. Live reflection cost remains unmeasured. [Panel traces, callback counts, and paired ranges](proposal-reflection-cap-results-v1.json)

The follow-up compared both supplied proposals within the zero-later-callback budget. [Opening pair replay](proposal-opening-pool.md)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_reflection_cap
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_reflection_cap \
  --execute 137728fb3cbaad822dc61e906612fa184afc587a70fc3aa2c9870a55be05b398 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each exercised 7,680 experimental cycles and reproduced 100 published panel traces. Six focused tests passed, including the funded opening, the hard callback limit, and full paired validation. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 6.0 GiB free. The 26.9 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_reflection_cap.py) · [Verification receipt](proposal-reflection-cap-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
