# Fund an independent retry after exact rejection

Use `qualify_with_funded_retry` at the admission step of an existing search. Pass its frozen nominee, the ordered `WitnessCycle` schedule, and the validation grades already paid for. The evaluator receives a prompt, a qualification `Row`, and repeat index zero, and returns an exact boolean. [Package API](../cpo/halving/funded_admission.py) · [Witness schedule](../cpo/rotating_witness/episode.py)

```python
from cpo.halving.funded_admission import qualify_with_funded_retry

result = qualify_with_funded_retry(
    incumbent,
    nominee,
    witness_cycles,
    qualify,
    paid_validation_grades,
    minimum_retry_lookups=14,
    evaluation_limit=24,
)

selected_prompt = result.prompt
proof_lookups = result.qualification_evaluations
```

`paid_validation_grades` maps `(prompt, row.id)` to a boolean for declared validation rows. Use one task family, distinct noncritical qualification rows, and up to 12 rows per panel. Keep qualification rows disjoint from validation and held-out rows. The first proof uses the nominee's assigned panel and can open up to `maximum_extension_rows` earlier rows on an exact tie. Supply `nominee=None` when search nominates nobody.

The first proof can use the entire combined cap. A promotion deploys immediately. After an exact rejection, the function tries at most one previously evaluated rival if the remaining cap meets `minimum_retry_lookups` and can fit its smallest possible promotion certificate. It prefers the rival's own panel, followed by the earliest available panel. It retires the entire first base panel and any used tie panel so the retry starts with separate evidence. An undecided proof retains the incumbent. `result.first` and `result.retry` contain the exact proof receipts when attempted. `result.retry_candidate` records the rival if a retry ran.

The 14-read gate passed on archived BBH and LMentry under a 24-lookup combined cap. The 12-read gate selected for MMLU failed its quality and cost checks. The caller chooses the gate. [Paired GEPA results](witness-funded-native-comparison.md)

## Replay the packaged API

The runner tests both thresholds on all 2,240 archived episodes. It checks the exact first and second proof receipts, physical callback order, deployed prompt, and charged lookups against the frozen benchmark. A clean source export and a separately installed CPO 0.4.0 wheel produced byte-identical reports. Fifty-three targeted tests passed from source and seven API tests passed from the installed wheel. The prospective live plan reproduced byte for byte. The replay blocked DNS and sockets and issued zero provider requests. Storage Guard measured 5.3 GiB free. The approximately 74 MiB source, build, and install overlays fit the standing 0.2 GiB LAB exception. [Replay receipt](witness-funded-admission-api-results-v1.json) · [API tests](../tests/unit/test_funded_admission.py)

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel for the archive runner.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_funded_admission_api
python -B -m benchmarks.witness_funded_admission_api \
  --execute 41b1553f0a5df3202e10f113745c26d62ba2162880514c37acc4fcc9d2c0288c \
  --out NEW_REPORT.json
```
