# Transferring the 12-case validation policy

The 12-case policy saved 21,793 lookups and finished one pass lower than 24-case CPO across the six transfer panels. It cleared both original full-budget GEPA gates on three panels. It missed the gate against both lower-budget GEPA controls on every panel. The adaptive CPO default remains in place. [Result and seal](prompteval-validation-transfer-results-v1.json)

## Frozen comparison

The 12-case, 52-lookup policy was selected from the earlier validation-size comparison. This replay fixes it before scoring the transfer runs. It uses three subjects outside both earlier validation-size cohorts, with a Llama and Mistral panel for each. The panels contain formal logic, high-school computer science, and world religions. Prior fixed-pool CPO experiments used these subjects. [Policy selection study](prompteval-validation-size.md) · [Recorded corpus](../benchmarks/data/prompteval-transfer-v1.json)

The comparison reuses the sealed four-cycle schedule, including 32 seeded episodes per model panel, 12 training cases, an eight-case qualification panel unique to each cycle, and a fixed final holdout. The smaller validation panel uses a prefix of the scheduled 24 cases. All search methods see the same proposals. Both official GEPA 0.1.4 controls receive the same 12-case panel, 52-lookup cap, and runner-up archive policy. Additional references use 24-case CPO at cap 88 and the ordinary 24-case GEPA controls at cap 171.

The transfer gate requires the candidate to match or improve exact holdout passes at no extra cost on every panel, with an accuracy gain or at least 10% savings on ties. It compares the candidate against each matched GEPA control separately. The benchmark also compares paired episode directions, which make decision changes visible even when total exact passes tie. The episodes reuse final holdout cases within a subject.

## Results

| Policy | Final passes | Paid lookups |
| --- | ---: | ---: |
| CPO, 12 cases and cap 52 | 4,479 | 40,203 |
| Sequential GEPA, same panel and archive | 4,483 | 31,157 |
| Batched GEPA, same panel and archive | 4,466 | 22,028 |
| CPO, 24 cases and cap 88 | 4,480 | 61,996 |
| Sequential GEPA, 24 cases and cap 171 | 4,461 | 62,051 |
| Batched GEPA, 24 cases and cap 171 | 4,481 | 61,350 |

The smaller CPO policy preserved or improved CPO's full-panel total on four panels. It lost eight passes on Mistral computer science and three on Mistral world religions. On the matched comparisons, the candidate returned 13 more aggregate passes than batched GEPA and used 18,175 more lookups. It returned four fewer passes than sequential GEPA and used 9,046 more lookups. Every matched panel comparison cost more under CPO.

Both offline runs returned identical reports. The result strengthens the evidence that smaller panels reduce CPO's own costs. It leaves the matched cost gap and live superiority open. [Runner](../benchmarks/prompteval_validation_transfer.py) · [Tests](../tests/test_prompteval_validation_transfer.py)

The follow-up exposed an opt-in qualification API that preserves these decisions while stopping early. [Paired qualification certificate](paired-qualification.md)

## Reproduce offline

Use pinned GEPA 0.1.4. Preview to obtain the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_validation_transfer
```
