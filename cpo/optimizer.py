"""Budgeted prompt search with paired validation and complementary candidates."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from random import Random


@dataclass(frozen=True)
class Row:
    id: str
    family: str
    critical: bool = False


@dataclass(frozen=True)
class Observation:
    passed: bool
    feedback: dict


@dataclass(frozen=True)
class Candidate:
    prompt: str
    passed: frozenset


@dataclass(frozen=True)
class Result:
    prompt: str
    evaluations: int
    reflections: int
    events: list


def balanced_order(rows, seed):
    rng = Random(seed)
    groups = defaultdict(list)
    for row in rows:
        groups[row.family].append(row)
    for group in groups.values():
        rng.shuffle(group)
    return [row for index in range(max(map(len, groups.values())))
            for group in groups.values() for row in group[index:index + 1]]


def search(initial, train, validation, evaluate, propose, *, metric_limit, rounds,
           train_per_round, proposals_per_round=2, seed=0, race=True, adaptive=False):
    """Evaluate precisely the supplied search rows. Feedback from validation stays private."""
    combined = [row.id for row in (*train, *validation)]
    if not train or not validation or len(set(combined)) != len(combined):
        raise ValueError('Search requires nonempty train and validation cohorts with distinct IDs')
    if metric_limit < len(validation) or min(rounds, train_per_round, proposals_per_round) < 1:
        raise ValueError('Search budget must cover initial validation and allow positive round limits')

    critical = {row.id for row in validation if row.critical}
    families = {row.id: row.family for row in validation}
    family_sizes = Counter(families.values())
    validation_ids = frozenset(families)
    probes = balanced_order(train, seed)
    events = []
    cache = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in cache:
            if len(cache) >= metric_limit:
                raise RuntimeError('Search evaluation budget exhausted')
            cache[key] = evaluate(prompt, row)
        return cache[key]

    def preference(prompt):
        return len(prompt), prompt

    def rank(candidate):
        counts = Counter(families[row_id] for row_id in candidate.passed)
        balance = sum(Fraction(counts[family], size) for family, size in family_sizes.items())
        return -len(candidate.passed & critical), -balance, -len(candidate.passed), preference(candidate.prompt)

    def dominates(candidate, possible, prompt):
        return candidate.passed > possible or (candidate.passed == possible
                                               and preference(candidate.prompt) <= preference(prompt))

    archive = [Candidate(initial, frozenset(row.id for row in validation if observe(initial, row).passed))]
    protected = archive[0].passed & critical
    events.append({'kind': 'validated', 'prompt': initial, 'passed': sorted(archive[0].passed)})
    attempted = {initial}
    cursor = 0
    reflections = 0
    successful_branch = 0
    for round_index in range(rounds):
        if archive[0].passed == validation_ids:
            break
        available = metric_limit - len(cache)
        # Reserve the seed-sized validation cost for at least one candidate in this round.
        probe_count = min(train_per_round, len(probes), available - len(validation))
        if probe_count < 1:
            break
        parent = archive[0]
        probes_this_round = [probes[index % len(probes)] for index in range(cursor, cursor + probe_count)]
        cursor += probe_count
        feedback = [(row, observe(parent.prompt, row)) for row in probes_this_round]
        history = [(candidate.prompt, dict(Counter(families[row_id] for row_id in sorted(candidate.passed))))
                   for candidate in archive[:3]]
        options = propose(parent.prompt, feedback, history, proposals_per_round)
        reflections += 1
        round_limit = min(metric_limit, len(cache) + max(len(validation),
                          (metric_limit - len(cache)) // (rounds - round_index)))
        branches = list(enumerate(options[:proposals_per_round]))
        if adaptive:
            # Spend on finishing a useful alternative before buying another reflection.
            future_probes = (rounds - round_index - 1) * train_per_round
            round_limit = max(len(cache) + len(validation), metric_limit - future_probes)
            branches.sort(key=lambda item: item[0] != successful_branch)
        for branch, prompt in branches:
            if not isinstance(prompt, str) or not prompt.strip() or prompt in attempted:
                continue
            if len(cache) >= round_limit:
                break
            reference = archive[0]
            ordered = sorted(validation, key=lambda row: (not row.critical, row.id in reference.passed))
            passed = set()
            remaining = set(validation_ids)
            status = 'validated'
            for row in ordered:
                if len(cache) >= round_limit and (prompt, row.id) not in cache:
                    status = 'budget'
                    break
                remaining.remove(row.id)
                if observe(prompt, row).passed:
                    passed.add(row.id)
                elif adaptive and row.id in protected:
                    status = 'critical_regression'
                    break
                if race and remaining and any(dominates(other, passed | remaining, prompt) for other in archive):
                    status = 'dominated'
                    break
            events.append({'kind': status, 'prompt': prompt, 'parent': parent.prompt,
                           'passed': sorted(passed), 'unobserved': sorted(remaining)})
            if status != 'budget':
                attempted.add(prompt)
            if status != 'validated':
                continue
            candidate = Candidate(prompt, frozenset(passed))
            if not any(dominates(other, passed, prompt) for other in archive):
                archive = [other for other in archive if not dominates(candidate, other.passed, other.prompt)]
                archive.append(candidate)
                archive.sort(key=rank)
            if archive[0].passed == validation_ids:
                break
            if adaptive and candidate.passed > parent.passed:
                successful_branch = branch
                break
    return Result(archive[0].prompt, len(cache), reflections, events)
