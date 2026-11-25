# Use first-gain certification in CPO

`run_first_gain_episode` runs the same validation-routed episode used by the published first-gain studies. Pass the incumbent, the ordered challengers and cases in each `EpisodeCycle`, an evaluator that returns an `Observation`, and an independent qualification callback. Both callbacks supply stable Boolean grades. [Implementation](../cpo/full_roster_precheck/first_gain.py) · [Episode inputs](validation-routed-episode.md)

```python
from cpo.full_roster_precheck.first_gain import run_first_gain_episode

result = run_first_gain_episode(
    incumbent,
    cycles,
    evaluate,
    qualify=qualify,
)
```

The policy nominates a challenger once its observed validation passes exceed the highest score the incumbent could still attain. Another challenger may have a higher complete score. Nomination leads to an independent qualification attempt. A rejection can switch the next cycle's schedule, and the result includes each cycle's schedule, nominee, deployment, and actual callback counts.

`uniform_read_limit` defaults to 18 and accepts an integer from 2 through 18. It applies to noncritical uniform screens with two challengers and three to six funded validation cases. Prepaid opening grades count toward it. The original screen and budget apply to other schedules and roster sizes. Distinct prompts and disjoint row IDs are checked across the entire episode before the first callback. [Focused tests](../tests/unit/test_first_gain_episode.py)

At 18 reads, the policy reduced lookups on both ARC-AGI groups while maintaining a positive held-out lead over affordable native GEPA and halving. It also saved 158 of 2,336 lookups across GSM8K and SST-5 with two fewer held-out passes than exact nomination. AIME still favored cheaper controls on observed quality per lookup. The offline evidence covers selection from shared archived prompts. [Math results](certified-strict-gain.md) · [Three-cycle results](certified-strict-gain-transfer.md)

## Reproduce the package comparison

Use Python 3.12, the hash-pinned GEPA 0.1.4 wheel, and the original Promptolution corpus. Run without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.certified_first_gain_api_parity \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 55587ef3dc5f3c861189f1c723d8d9ab0207002fcbcd7c516e1b32cfc584c047 \
  --out NEW_REPORT.json
```

The package matched the benchmark across 824 archived episodes and 2,408 paired policy runs. The comparison checks each ordered callback, returned cycle result, and held-out score and cost total. The source checkout and an isolated wheel install produced byte-identical receipts at SHA-256 `e925474dbc13eb4564f5645a856ae313a7bcb50309cbe5636c4ecd63bbc0e585`. All 30 focused tests passed from source, and the four new API tests passed from the installed wheel. The CLI refused a stale seal and an existing output. The earlier certified-nomination prospective plan reproduced its published seal. Both replays blocked sockets and DNS and sent zero provider requests. Storage Guard measured 8.8 GiB free, and the bounded workspace occupied 126 MiB under the standing LAB exception. [Parity runner](../benchmarks/certified_first_gain_api_parity.py) · [Sealed receipt](first-gain-episode-parity-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
