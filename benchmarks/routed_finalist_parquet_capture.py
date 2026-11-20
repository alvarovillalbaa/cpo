"""Read the frozen transfer panels directly from the pinned dataset revision."""

import argparse
from hashlib import sha1, sha256
from importlib.metadata import version
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote
from unittest.mock import patch

from benchmarks import routed_finalist_model_transfer as study
from benchmarks.independent_mmlu_transfer import DATASET, REVISION, check_revision, get_public, read_json, rows_url
from cpo._contract import digest


HUB = 'https://huggingface.co'
DECODER_VERSION = '1.4.3'


def published_panel(subject, model, metadata, directory, connection):
    name = f'{subject}/{model}-00000-of-00001.parquet'
    item = metadata[name]
    url = f'{HUB}/datasets/{DATASET}/resolve/{REVISION}/{quote(name, safe="/")}'
    raw = get_public(url)
    content_sha256 = sha256(raw).hexdigest()
    if item.get('lfs'):
        expected, actual = item['lfs']['oid'], content_sha256
    else:
        expected = item['oid']
        actual = sha1(f'blob {len(raw)}\0'.encode() + raw, usedforsecurity=False).hexdigest()
    if len(raw) != item['size'] or actual != expected:
        raise ValueError(f'The fetched Parquet file differs from the pinned Git object for {name}')
    file = directory / f'{subject}-{model}.parquet'
    with file.open('xb') as handle:
        handle.write(raw)
    relation = connection.read_parquet(str(file))
    columns, rows = relation.columns, relation.fetchall()
    if (columns != [f'example_{i}' for i in range(len(columns))] or len(rows) != 100 or
            any(type(value) is not int or value not in (0, 1) for row in rows for value in row)):
        raise ValueError('The source must contain 100 ordered templates and exact binary outcome columns')
    return {'subject': subject, 'model': model, 'correctness': [''.join(map(str, row)) for row in rows],
            'caseOrderSha256': digest(columns), 'rowsUrl': rows_url(subject, model),
            'sourceParquet': {'url': url, 'gitOid': item['oid'], 'sha256': content_sha256, 'bytes': len(raw)}}


def tree(subject):
    url = f'{HUB}/api/datasets/{DATASET}/tree/{REVISION}/{quote(subject)}'
    return {item['path']: item for item in read_json(get_public(url)) if item['type'] == 'file'}


def capture(plan, directory, connection):
    check_revision()
    panels = []
    for subject in study.SUBJECTS:
        metadata = tree(subject)
        panels.extend(published_panel(subject, model, metadata, directory, connection) for model in study.MODELS)
    check_revision()
    snapshot = {'sourceDataset': DATASET, 'observedRepoRevision': REVISION, 'license': 'MIT',
                'designSha256BeforeCapture': digest(plan), 'panels': panels}
    with patch.object(study.transfer, 'EXPECTED', study.EXPECTED):
        study.transfer.check_corpus(snapshot, plan)
    return snapshot


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute', required=True)
    cli.add_argument('--out', type=Path, required=True)
    args = cli.parse_args()
    plan = study.design()
    expected = {'design': plan, 'designSha256': digest(plan)}
    if (args.execute != expected['designSha256'] or read_json(study.DESIGN.read_bytes()) != expected
            or args.out.exists()):
        cli.error('Capture requires the unchanged frozen design and a fresh output path')
    if version('duckdb') != DECODER_VERSION:
        raise ValueError('Use the pinned DuckDB decoder in a temporary environment')
    import duckdb

    with TemporaryDirectory(prefix='cpo-routed-parquet-') as temporary, duckdb.connect(':memory:') as connection:
        connection.execute('SET threads=1')
        connection.execute('SET preserve_insertion_order=true')
        snapshot = capture(plan, Path(temporary), connection)
    with args.out.open('x') as output:
        json.dump(snapshot, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
