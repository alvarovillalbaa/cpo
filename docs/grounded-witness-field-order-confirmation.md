# Run reordered confirmation with early rejection

The field-order benchmark found that persistent shared errors on any of its 12 reordered cases passed the existing paired gate. This separate confirmation runner binds those cases to an exact, qualifying ordered development archive. It keeps the selected prompts, both search-cost measures, the paired gate, and the request ceiling. The added gate requires one exact CPO reply out of two for every reordered case. [Field-order benchmark](witness-confirmation-field-order.md) · [Runner](../benchmarks/grounded_witness_field_order_confirmation.py)

Before each dispatch, the runner can reject if the existing paired gate has become impossible or if a reordered case can no longer earn its required exact reply. A case-level stop records the failed case, the paid prefix, and the first unsent request hash. The paired verdict is unmeasured if the case-level rule stops it first. A successful confirmation completes the whole panel. Exact replay verifies the plan, wire journal, and result against the bound development archive.

| Fixture | Scored requests out of 128 | Result |
| --- | ---: | --- |
| Replies independent of field order | 128 | Qualified |
| One failed repeat on every reordered case | 128 | Qualified |
| Both repeats failed on one reordered case, across 12 trials | 3 to 114 | 12 early rejections |

Every persistent-failure trial stopped immediately after its second failed CPO repeat. This avoided 14 to 125 requests per trial compared with finishing the panel. The default persistent-failure fixture stopped at 108, and its archive replayed byte for byte. Both qualifying archives also replayed exactly. Thirty-seven targeted tests passed with sockets and DNS blocked. They rejected a stale seal, a delivery mismatch, and a changed result. [Fixture plan](grounded-witness-field-order-confirmation-plan-v1.json) · [Rehearsal receipt](grounded-witness-field-order-confirmation-rehearsal-v1.json)

The published ordered development and Luna SDK plan previews both matched their existing manifests. The portable rehearsal sent zero provider requests and leaves the live comparison unverified. Storage Guard measured 5.9 GiB free. The 39 MiB export, fixtures, and publication worktree fit the standing 0.2 GiB LAB exception.

## Luna SDK confirmation

A separate Luna adapter binds the check to the six files of a qualifying ordered development archive. The mock development paused after 400 count-and-generation pairs and resumed before binding confirmation. In Python 3.12.14 with OpenAI 2.44.0 and HTTPX 0.28.1, both passing fixtures completed 128 mock pairs. The earliest and latest persistent failures ended at 3 and 114. All four SDK archives replayed byte for byte. Two rehearsals produced identical receipts. The fixture reservation was $0.983040 at plan rates. The rehearsal sent zero provider requests. [SDK receipt and fixture plan](grounded-witness-field-order-sdk-rehearsal-v1.json)

## Reproduce

Use a clean checkout with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.grounded_witness_ordered_futility \
  --fixture ce048ab5da16f4b3a4162ddc67097a6e16717826afb2236170b08a6b63a866dc \
  --out ordered-development
python -B -m benchmarks.grounded_witness_field_order_confirmation \
  --development ordered-development \
  --fixture 2c926c060e3053469b51b674bb7b46d2362d9ac8a3fee8cdb25f11b1cf1f655e \
  --profile shared-failure --out field-order-confirmation
python -B -m benchmarks.grounded_witness_field_order_confirmation \
  --development ordered-development \
  --replay field-order-confirmation --out field-order-replayed
```
