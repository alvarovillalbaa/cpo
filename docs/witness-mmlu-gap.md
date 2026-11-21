# Locate CPO's remaining MMLU gap

The paired CPO comparison cleared the BBH and LMentry gate. Both MMLU cohorts crossed zero, and a hindsight allocation of native GEPA across subjects led the pooled MMLU score. This follow-up reruns the exact cap-16 CPO selector on the 832 enrolled MMLU episodes. It uses the same starts, enrolled prompts, case splits, and admission policy. It compares each episode with the previously selected fixed GEPA setting for its cohort and the pooled hindsight GEPA setting for its subject. [Paired comparison](witness-cached-gepa-evidence.md) · [Attribution runner](../benchmarks/witness_mmlu_gap.py)

An episode records whether the witness or fallback submitted and passed admission, exhausted its search cap, or finished without a nominee. Native disagreements are grouped by those outcomes and by whether one or both methods deployed a new prompt. A recorded paired validation win requires both paid grades on the same case. The challenger must pass where the incumbent failed.

| Outcome against the hindsight GEPA allocation | Episodes | Net native passes |
| --- | ---: | ---: |
| Same deployment | 672 | 0 |
| Native retained the start | 113 | −27 |
| Both promoted different prompts | 20 | +26 |
| Native promoted after CPO's witness admission failed | 16 | +54 |
| Native promoted after CPO's fallback admission failed | 3 | +2 |
| Native promoted after CPO exhausted its fallback cap | 4 | +13 |
| Native promoted after CPO found no nominee | 4 | +8 |
| Total | 832 | +76 |

CPO submitted 539 proofs. The 405 rejections used 7,358 of the 9,500 admission lookups. In the 16 episodes where GEPA promoted after a witness rejection, seven GEPA deployments already had a CPO validation grade. None had a paid paired win. Those episodes contributed 54 of the 76 net passes for the hindsight allocation. Relative to the two fixed native controls, CPO gained 21 raw passes across the cohorts. [Stage counts and native trace checks](witness-mmlu-gap-results-v1.json)

## Budget-neutral headroom

The audit freezes every paid search lookup. It measures several choices for the one admission slot. Retention chooses between the original outcome and keeping the start. The wider menus also offer challengers with a paid paired win, any paid validation grade, or any roster position. Each alternative must pass the original independent proof on its enrolled cases within the episode's actual proof spend. Its reserve starts with the earlier unspent admission panels. Episodes with zero proof spend have no allowance for a new admission. The audit uses holdout outcomes after pricing and qualification to rank the feasible options. These figures are hindsight ceilings for the enumerated menus. The proof spend is known retrospectively.

| Menu | Extra passes on nine prior subjects | Extra passes on four additional subjects | Pooled extra passes |
| --- | ---: | ---: | ---: |
| Retain or use the original deployment | 78 | 58 | 136 |
| Add challengers with paid paired wins | 136 | 89 | 225 |
| Add any already-evaluated challenger | 510 | 225 | 735 |
| Allow every enrolled challenger | 816 | 362 | 1,178 |

The already-evaluated menu adds 599 passes beyond the retention ceiling and 510 beyond the paid paired-win menu. It isolates a question for the next comparison. A selector must choose among already-evaluated nominees with only their paid evidence and a proof allowance available before dispatch. This audit measures the room for such a selector. It used zero provider requests. [Frozen ceilings by subject](witness-mmlu-gap-results-v1.json)

The follow-up tested three rankings on the existing paid evidence. They changed just one of 539 MMLU nominations and produced no net gain. [Paid nominee ranking replay](witness-paid-nominee-ranking.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel from a clean source export. Two full replays produced byte-identical reports, and the earlier CPO scores, costs, native traces, and original live plan reproduced. Twelve targeted tests passed with DNS and sockets blocked. Storage Guard measured 5.9 GiB free. The task-owned export and wheel overlay fit the standing 0.2 GiB LAB exception and were removed. [Proof-budget and attribution tests](../tests/unit/test_witness_mmlu_gap.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_mmlu_gap
python -B -m benchmarks.witness_mmlu_gap \
  --execute 0812b9617de3651cf6c2382059134d840ded56bc40982612f327c0c05fe3e34b \
  --out NEW_REPORT.json
```
