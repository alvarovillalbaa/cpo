"""Classify exact-object replies without coercing fields or values."""

from hashlib import sha256
import json


def digest(value):
    return sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('JSON object contains duplicate keys')
    return result


def classification(text, expected, *, strict=True):
    try:
        result = json.loads(text, object_pairs_hook=unique_object if strict else None)
    except ValueError:
        return 'invalid_json'
    if not isinstance(result, dict) or result.keys() != expected.keys():
        return 'wrong_keys'
    if any(type(result[key]) is not type(value) for key, value in expected.items()):
        return 'wrong_types'
    return 'pass' if result == expected else 'wrong_values'
