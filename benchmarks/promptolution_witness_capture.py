"""Rebuild the pinned Promptolution archive from recorded public predictions."""

import argparse
import csv
from hashlib import sha1, sha256
from io import StringIO
import json
from pathlib import Path
from urllib.request import urlopen

from benchmarks.promptolution_witness_episode import CAPTURE_DESIGN, TASKS, load_corpus
from cpo._contract import digest


REPOSITORY = 'finitearth/prompt-optimization-framework-comparison'
REVISION = '6cd48d2431bb5cf796273f4ea10d3119791ec483'
MODEL = 'gemma-3-27b-it'
OBJECTS = {
    'gsm8k': {
        'AdalFlow': ('run_adalflow', 87980, '841007e6c6634f9a801d9d21790a98f3249a0893'),
        'CAPO': ('run_CAPO', 73796, '8ff2761bdd58b3a89770b8399364a333303f4739'),
        'DSPy-GEPA': ('run_DSPY', 79310, '3a0f74b365bdbcdd09c0ac35e73e08304028ec5e'),
        'OPRO': ('run_OPRO', 74109, '2d294afe021f8fb6f245489894fce6f9eb6299dc'),
        'unoptimized': ('run_unoptimized', 74356, 'c170e2be25efd38057de4499f2c84b55af456575'),
        'unoptimized2': ('run_unoptimized2', 74935, '5f448bb6017cf59105c44d2137136f2d38f9064b'),
        'unoptimized3': ('run_unoptimized3', 73877, 'a4c61d34550eb3cd203ab08635bfa9db9ad70d93'),
    },
    'sst5': {
        'AdalFlow': ('run_adalflow', 37721, 'e00b6611b8a3b9bb60963c2ae98f41582da32f16'),
        'CAPO': ('run_CAPO', 37798, 'f8c284dc866366e622ec66eef62aa226e28f1b0f'),
        'DSPy-GEPA': ('run_DSPY', 38792, '07991f7bd8dfb3d1fd0a1f8fb608edfd04f28dd8'),
        'OPRO': ('run_opro', 37856, '1b143eeaabb3c0da3a5e1bcc32f2a51ea7f8c281'),
        'unoptimized': ('run_unoptimized', 42198, 'b12faf549bdaa76cd250ffece1724655a2e8309e'),
        'unoptimized2': ('run_unoptimized2', 37652, 'dd79457c1fd1e2fed7b76241b0df53ddfc56848a'),
        'unoptimized3': ('run_unoptimized3', 37746, 'ea367a9c7f8a579005193fb9afa1213f17cf6983'),
    },
}


def decode(raw, size, blob):
    if len(raw) != size or sha1(f'blob {size}\0'.encode() + raw).hexdigest() != blob:
        raise ValueError('Prediction bytes differ from the pinned Git object')
    reader = csv.DictReader(StringIO(raw.decode('utf-8'), newline=''))
    if reader.fieldnames != ['input', 'target', 'prediction_raw', 'correct']:
        raise ValueError('Unexpected prediction columns')
    questions, cases = set(), {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError('Expected the same four prediction fields on every row')
        question, target = row['input'], row['target'].strip()
        correct = row['correct']
        if (not question.strip() or not target or question in questions or
                correct != str(int(row['prediction_raw'].strip() == target))):
            raise ValueError('Prediction cases must be unique and agree with their exact-match flags')
        questions.add(question)
        cases[digest((question, target))] = correct
    if len(cases) != 300:
        raise ValueError('The archive requires every original case')
    return cases


def capture():
    archive = {}
    for task in TASKS:
        aligned, vectors, sources = None, {}, {}
        for program, (folder, size, blob) in OBJECTS[task].items():
            url = f'https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/results_eval/{task}/{MODEL}/{folder}/predictions.csv'
            with urlopen(url, timeout=20) as response:
                raw = response.read(size + 1)
            cases = decode(raw, size, blob)
            aligned = sorted(cases) if aligned is None else aligned
            if set(aligned) != cases.keys():
                raise ValueError('Public programs did not cover the same question and target pairs')
            vectors[program] = ''.join(cases[case] for case in aligned)
            sources[program] = {'gitBlobSha1': blob, 'sha256': sha256(raw).hexdigest(), 'bytes': size}
        archive[task] = {'caseIDs': aligned, 'correctness': vectors, 'sources': sources}
    reduced = (json.dumps({'designSha256': CAPTURE_DESIGN, 'archive': archive}, sort_keys=True) + '\n').encode()
    load_corpus(reduced)
    return reduced


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a fresh archive path')
    data = capture()
    with args.out.open('xb') as output:
        output.write(data)


if __name__ == '__main__':
    main()
