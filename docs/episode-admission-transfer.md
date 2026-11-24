# Separate CPO's episode retention and wider-search effects

The [two-check episode rule](episode-training-probe-transfer.md) gained 24 passes and saved 794 lookups on four-case MMLU. It made two changes to the bounded opening. It retained the starting prompt after two incumbent training passes and chose eight-challenger halving after exactly one pass. This replay isolates those changes. Both isolated arms buy the same two training replies. The runner verifies that their effects on final passes and on search and qualification lookups add up to the combined effect on every episode. Probe charges are accounted for separately because the combined rule buys the shared prefix once. [Runner](../benchmarks/episode_admission_transfer.py)

The new early-stop rule retains only when all required incumbent training cases pass. A miss immediately sends the episode to the bounded opening, skipping the remaining training cases. The replay compares required prefix lengths of one through four. Validation and independent qualification keep their original cases and gates. [Admission rule](../cpo/episode_admission.py)

## Discovery

The fit uses the same 70 panels from 31 discovery tasks and excludes all target tasks. Every candidate charges its actual training probes. To be eligible for selection, it must fit the bounded opening's original lookup budget in each discovery cohort.

| Rule | Discovery passes / lookups | Fits every budget |
| --- | ---: | --- |
| Bounded opening | 84,043 / 67,022 | Yes |
| Combined two-check rule | 84,026 / 61,618 | Yes |
| Retention only, both checks paid | 83,924 / 54,433 | Yes |
| Wider search only | 84,145 / 78,687 | No |
| Retain after one pass | 83,738 / 40,954 | Yes |
| Retain after two passes, stop on a miss | 83,924 / 53,376 | Yes |
| Retain after three passes, stop on a miss | 83,956 / 59,665 | Yes |
| Retain after four passes, stop on a miss | 83,990 / 63,663 | No |

The wider-search change adds 102 passes and exceeds every cohort's budget. The two-pass retention change loses 119 passes. Stopping on the first miss saves 1,057 training lookups while preserving the eager retention path. The discovery fit selects the bounded opening. [Frozen fit](episode-admission-fit-v1.json)

## Target replay

Cells give final passes and paid lookups, including routing probes. The replay reproduces the original combined and bounded opening scores and costs. The first-miss rule preserves every deployment of eager two-pass retention while reading 1,112 fewer training replies across the replay.

| Cohort | Bounded opening | Combined two checks | Wider search only | Two-pass retention, early stop | Four-pass retention, early stop |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,421 | 6,335 / 13,212 | 6,362 / 16,465 | 6,320 / 10,750 | 6,341 / 13,138 |
| Bounded LMentry | 6,338 / 15,636 | 6,313 / 15,502 | 6,379 / 17,392 | 6,272 / 14,243 | 6,320 / 15,431 |
| Bounded MMLU | 7,719 / 6,554 | 7,721 / 5,275 | 7,723 / 8,101 | 7,717 / 4,144 | 7,719 / 5,928 |
| Four-case MMLU | 22,369 / 10,591 | 22,393 / 9,797 | 22,398 / 12,807 | 22,364 / 8,193 | 22,369 / 10,334 |
| Tie BBH | 2,145 / 12,521 | 2,131 / 13,165 | 2,139 / 13,916 | 2,137 / 12,084 | 2,140 / 12,816 |
| Tie LMentry | 992 / 6,971 | 991 / 7,042 | 990 / 7,257 | 993 / 6,904 | 992 / 7,126 |
| Additional MMLU | 7,398 / 6,354 | 7,396 / 5,600 | 7,397 / 7,902 | 7,397 / 4,467 | 7,400 / 5,803 |
| **Pooled** | **53,308 / 72,048** | **53,280 / 69,593** | **53,388 / 83,840** | **53,200 / 60,785** | **53,281 / 70,576** |

On four-case MMLU, wider search adds 29 passes, with a paired 95% range of +15 to +44. It uses 2,216 more lookups. Retention gives up five of those passes and cuts enough search to put the combined rule 794 lookups below the bounded opening. On bounded LMentry, wider search contributes 41 passes, while retention loses 66, leaving the combined rule 25 passes behind.

Early-stop two-pass retention skips search in 558 of 2,048 episodes and fits every target budget. It saves 11,263 lookups and loses 108 passes relative to the bounded opening. Wider search alone gains 80 pooled passes, exceeds the bounded opening's spend in all seven cohorts, and exceeds the task-tuned GEPA upper bound in six at its realized cost. It remains below the task-tuned simple point score in every cohort. These totals describe the archive because some tasks recur.

The two-probe result on four-case MMLU depends on spending more on selected episodes and less on retained episodes. Early termination makes the retention decision cheaper, while the fit still favors the bounded opening. Fresh live superiority remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.episode_admission_transfer --fit \
  --execute 46717233fb26dc18a24e651802e3ce9479a54f3168f82af31a0fe25e0d626b04 \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.episode_admission_transfer \
  --cohort four-case-MMLU --fitted NEW_FIT.json \
  --execute 0b985310c2b6da29e5504fa810ec9d77865de6d4748809a02568672fb247a472 \
  --out NEW_REPORT.json
```

[Bounded BBH](episode-admission-transfer-bounded-bbh-v1.json) · [Bounded LMentry](episode-admission-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](episode-admission-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](episode-admission-transfer-four-case-mmlu-v1.json) · [Tie BBH](episode-admission-transfer-tie-bbh-v1.json) · [Tie LMentry](episode-admission-transfer-tie-lmentry-v1.json) · [Additional MMLU](episode-admission-transfer-additional-mmlu-v1.json)

Forty-one targeted tests passed. Duplicate fits and target replays matched byte for byte with DNS and outbound sockets blocked. The replay verified the original bounded opening's paid trajectories and the episode-level attribution. It made zero provider requests. Storage Guard measured 9.6 GiB free. The source export, dependency overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_episode_admission.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
