# Stop scoring when paired opening cannot qualify

On two scripted development runs, the paired-opening candidate became ineligible after 26 of 324 scoring requests and 93 of 288. In both cases, an observed critical loss against sequential GEPA made rejection permanent. The scripted qualifying run needed all 216 development scoring requests and all 96 confirmation requests. [Results and archive hashes](grounded-staged-paired-opening-futility-results-v1.json)

| Fixture | Stage | Requests through verdict | Full scoring requests | Requests the rule would omit |
| --- | --- | ---: | ---: | ---: |
| All rewrites faulted | Development | 26 | 324 | 298 (92.0%) |
| Perfect ticket rewrite | Development | 93 | 288 | 195 (67.7%) |
| Rewrite only | Development | 216 | 216 | 0 |
| Rewrite only | Confirmation | 96 | 96 | 0 |

Once prompts are selected, every case and repeat has one physical request per distinct prompt. The bound gives every unseen candidate request a pass and every other unseen request a fail. Arms sharing a request receive the same grade. This assignment simultaneously maximizes candidate task totals, paired margins, and the chance of preserving each critical pass. If the bound fails the existing gate, every completion fails it. The scoring function still requires the full panel for a positive verdict. [Scoring function](../benchmarks/grounded_staged_paired_opening_futility.py) · [Exhaustive completion tests](../tests/unit/test_grounded_staged_paired_opening_futility.py)

The replay matches every physical scoring request and paired grade from the unchanged shared-sample protocol. It applies the existing logical search-use gate to the recorded fixture replies. Tests also require both the call-count gate and a separate fixed search-charge gate on small exhaustive panels. The projected scores at rejection are upper-bound inputs to that verdict. Omitted scores would remain unknown. The full offline fixture runs generated the reference replies, so the omissions are replay estimates. The published SDK plan still uses the original full schedule. Live savings and fresh-model quality have yet to be measured. [Sealed SDK budget and protocol](grounded-staged-paired-opening-budget.md)

## SDK dispatch rehearsal

A fixture-only guard applied the same proof before writing the next scoring request in either journal. The actual OpenAI Python SDK 2.44.0 and HTTPX 0.28.1 routed requests to an in-process mock transport with DNS and sockets blocked. Before scoring, the guard charged logical uses and attributed token costs separately. It grouped identical samples and reconciled the per-arm charges with the completed fixture's independent receipt audit.

The guard sent 328 total mock HTTP requests for the all-rewrites-faulted fixture and 355 for the perfect-ticket-rewrite fixture. It omitted the final 298 and 195 scoring requests respectively. In both cases the provider and comparison journals matched the same complete-reply prefix of the original fixture byte for byte. The qualifying rewrite-only fixture completed all 366 development requests and all 96 confirmation requests, reproducing both archives byte for byte. [SDK rehearsal receipt](grounded-staged-paired-opening-futility-sdk-rehearsal-v1.json)

## Sealed SDK terminal rejection

The separate SDK seal `46e1381439661d28cc741b43c2b76a6ed57aa24fff12f6c5f9422c9e80dc9e85` adds predispatch rejection while retaining the 1,596-request ceiling and the existing model, arms, cases, and gates. A terminal result records the observed scoring count, the schedule and observed-grade hashes, the first unsent sample hash, and the bounds that prove rejection. Both request journals end on complete replies. Exact replay regenerates the terminal receipt, and a rejected development archive cannot bind a confirmation. [Sealed-runner verification](grounded-staged-paired-opening-futility-sdk-runner-results-v1.json)

In both rejected development fixtures, the runner reproduced the entire terminal archive from a checkpoint one request before the cutoff. Each resume dispatched exactly one new mock request. A second resume attempt failed. A changed unsent-sample hash caused replay to reject the terminal receipt. The qualifying fixture reproduced its complete development archive across a checkpoint, then used all 96 independent confirmation requests. A faulted confirmation stopped after nine requests because its task pass floor was unreachable. These results use mock SDK responses. Live inference remains paused.

## Reproduce

Use Python 3.12 and hash-pinned GEPA 0.1.4. Export the sealed v6 controls and overlay the paired-opening, budget, and replay sources. Verification used DNS and socket blocking with task-owned temporary files bounded at 0.2 GiB under the standing LAB exception. Storage Guard measured 7.2 GiB free. [Benchmark requirement](../requirements-benchmark.txt)

```sh
cpo_checkout=$(pwd)
replay_dir=$(mktemp -d)
git archive 949dfe5e0971ce884b85026c76d1f96ad88e7ae0 | tar -xf - -C "$replay_dir"
mkdir -p "$replay_dir/cpo/paired_opening"
cp "$cpo_checkout/cpo/paired_opening/__init__.py" "$replay_dir/cpo/paired_opening/"
cp "$cpo_checkout/benchmarks/grounded_staged_paired_opening_comparison.py" \
  "$cpo_checkout/benchmarks/grounded_staged_paired_opening_budget.py" \
  "$cpo_checkout/benchmarks/grounded_staged_paired_opening_futility.py" "$replay_dir/benchmarks/"
(
  cd "$replay_dir" || exit
  PYTHONHASHSEED=0 python -B -m benchmarks.grounded_staged_paired_opening_futility \
    --execute 05f3a8efbb35a4a9e5357b56cb0803a03dc02b049f4d94a2bcd1011d454be070 \
    --out "$cpo_checkout/NEW_REPORT.json"
)
```

The results SHA-256 is `a65523177bda8d2de5e712de3e83ce162aaa932309089949389eef35f5f97d25`.
