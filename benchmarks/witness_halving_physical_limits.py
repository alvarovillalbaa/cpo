"""Derive the physical request ceiling for the sealed Halving futility plan."""

from hashlib import sha256
import json
from pathlib import Path

from benchmarks import grounded_witness_halving_futility as futility
from cpo._contract import digest


PORTABLE = 'aae517e6c51cf57645d0f788beb8d86fcc90f59a6a91ac6f85e2c3ba64ecaea0'


def halving_shape(limit):
    """Return the first prefix width and scheduled grades for three prompts."""
    first = limit // 6
    return first, 3 * first + 2 * ((limit - 3 * first) // 2)


def prepare():
    groups, plan, _ = futility.prepare()
    if digest(plan) != PORTABLE:
        raise ValueError('The physical bound applies only to the published portable futility plan')
    cycles = plan['cycles']
    parent = futility.parent
    original = parent.original
    anchors = plan['gepaValidationAnchors']
    task_count = len(groups)
    witnesses = (*original.CPO, parent.CANDIDATE)
    attempts = plan['maxAdmissionAttempts']
    repeats = plan['repeats']

    # Both native modes seed all eight original-prompt anchors on every live cycle.
    native_union = anchors + cycles * sum(plan['perCycleSearchCaps'][mode] - anchors for mode in original.GEPA)
    (prefix, small), (extended, large) = [halving_shape(cap) for cap in sorted(plan['halvingLogicalCaps'].values())]
    if extended > anchors:
        raise ValueError('Halving seed coverage differs from the audited envelope')
    # The scheduled first prefixes overlap, even when a certificate skips a grade.
    both_halving = small + large - 3 * prefix - extended
    halving_union = cycles * max(both_halving, small - prefix, large - extended)
    witness_union = cycles * max(plan['perCycleSearchCaps'][name] for name in original.CPO)
    additional_fallback = plan['fallbackNewEvaluationLimitPerTask']
    proofs = max(attempts[name] for name in witnesses) + sum(attempts[name] for name in plan['arms'] if name not in witnesses)
    per_task = {'reflection': cycles, 'evaluation': native_union + halving_union + witness_union + additional_fallback,
                'admission': proofs * 2 * (plan['splitSizes']['admission'] // cycles) * repeats,
                'qualification': len(plan['arms']) * plan['splitSizes']['holdout'] * repeats}
    limits = {role: amount * task_count for role, amount in per_task.items()}
    if any(limit > plan['physicalLimitsByRole'][role] for role, limit in limits.items()):
        raise ValueError('The new physical limit exceeds the original envelope')
    return {'protocol': 'grounded-witness-halving-physical-limits-v1', 'portablePlanSha256': PORTABLE,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'taskCount': task_count,
            'lookupsPerTask': per_task, 'evaluationComponentsPerTask': {'GEPA': native_union, 'Halving': halving_union,
                'witness': witness_union, 'fallback': additional_fallback},
            'independentProofsPerTask': proofs, 'maxDistinctScoringPromptsPerTask': len(plan['arms']),
            'maxRequestsByRole': limits, 'maxRequests': sum(limits.values()),
            'parentPhysicalLimitsByRole': plan['physicalLimitsByRole']}


if __name__ == '__main__':
    print(json.dumps(prepare(), indent=2, sort_keys=True))
