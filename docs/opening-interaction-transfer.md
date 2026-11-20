# Transfer routed repair to overlapping rules

The [fallback probe comparison](opening-probe-fallback.md) used fields determined by individual input attributes. This experiment gives each output field two inputs and introduces overlapping exceptions. A scripted proposer can correct only one observed table entry per call. Correcting three exceptions takes three proposals, even when one training case exposes all three.

The comparison uses 36 new panels across venue access, dispatch, and archive retention. Each panel splits 66 distinct input combinations into training, validation, qualification, and holdout. Every split contains all nine combinations for each required pair. The shared rewrite starts with one, two, or three wrong entries. Each exact score checks the complete JSON response. All optimizers receive the same evaluator, opening pair, 56-lookup search cap, and labeled training rows. The proposer reads measured training failures to select a single edit. It has no qualification or holdout cases. Demonstration bundles are inert in this fixture. [Runner and corpus generator](../benchmarks/opening_interaction_transfer.py)

The primary arm uses the released routed cycle with stall recovery and 12 fallback probes. It gives the router singleton features and all six pairwise combinations. The matched CPO arm uses singletons with the same repair policy. Native sequential and batched GEPA use exact-first field scores and the same scripted proposer. Separate qualification uses the existing paired certificate for both GEPA controls and for the routed arms.

| Method | One exception passes / calls | Two overlapping exceptions passes / calls | Three exceptions passes / calls | Total passes / calls |
| --- | ---: | ---: | ---: | ---: |
| CPO, singleton features | 216 / 884 | 204 / 973 | 186 / 992 | 606 / 2,849 |
| CPO, singleton and pair features | 216 / 884 | 210 / 992 | 188 / 1,015 | 614 / 2,891 |
| Sequential GEPA | 214 / 1,020 | 188 / 966 | 164 / 953 | 566 / 2,939 |
| Batched GEPA | 192 / 911 | 176 / 867 | 158 / 880 | 526 / 2,658 |

The primary arm cleared both GEPA gates on the one-exception panels. Across all profiles, it gained 48 passes and saved 48 calls against sequential GEPA, but lost one matched critical pass. The archive panel at seed `62723` tied sequential GEPA at 16 of 18 with different passing cases. Its first training batch passed every probe. The remaining stage supplied one repair for two incorrect entries. The primary arm gained 88 passes over batched GEPA with no paired critical losses and spent 233 more calls, so it also missed that gate. Pair features added eight passes and 42 calls over singleton routing, with nine matched critical losses. This result leaves automatic pair expansion experimental. [Sealed results and panel receipts](opening-interaction-transfer-results-v1.json)

## Reproduce offline

Use GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_interaction_transfer
PYTHONHASHSEED=0 python -B -m benchmarks.opening_interaction_transfer \
  --execute 6ed7f2087fdae3dfb9e63379f4c94b03bd155c48c9b9df1fa3ab557665d6c401 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each ran 36 scripted panels and 72 native GEPA paths. Sixteen focused tests passed. The runner rejected an altered seal and preserved an existing report. Storage Guard measured 4.6 GiB free and the 29.5 MB scratch export was removed under the standing LAB exception. Live accuracy on interacting rules remains unmeasured. [Verification receipt](opening-interaction-transfer-verification-v1.json)

## Early fallback pilot

An exploratory run allowed fallback on the first passing batch if two full validation panels and one later training probe could still be funded. It ran on the same 36 panels. CPO with pair features scored 616 passes in 2,909 calls and recovered the matched critical loss against sequential GEPA. The minimum panel score still blocked the sequential gate, and batched GEPA still used 251 fewer calls. [Pilot patch](../benchmarks/patches/interaction-early-fallback.patch)

To reproduce the pilot, apply the patch in a disposable export of `8956f4a95291ffa98cd65b3b186693b3200736a5`. Run the benchmark preview there and use the new seal printed for the patched source.
