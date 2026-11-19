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
    fields: int = 0


@dataclass(frozen=True)
class Observation:
    passed: bool
    feedback: dict
    matched_fields: int = 0


@dataclass(frozen=True)
class ProposalPair:
    """A complete rewrite and a focused repair from the same training evidence."""

    rewrite: str
    repair: str


@dataclass(frozen=True)
class ProposalBatch:
    """Ordered prompts from a source that can declare a parent's queue exhausted."""

    prompts: tuple[str, ...]
    exhausted: bool = False


@dataclass(frozen=True)
class Candidate:
    prompt: str
    passed: frozenset
    matched_fields: int = 0


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
           train_per_round, proposals_per_round=2, seed=0, race=True, adaptive=False, field_credit=False,
           opening_pair=None):
    """Search supplied rows. A precomputed pair uses the first round without a reflection.

    Feedback supplied to propose comes only from training.
    """
    combined = [row.id for row in (*train, *validation)]
    if not train or not validation or len(set(combined)) != len(combined):
        raise ValueError('Search requires nonempty train and validation cohorts with distinct IDs')
    if metric_limit < len(validation) or min(rounds, train_per_round, proposals_per_round) < 1:
        raise ValueError('Search budget must cover initial validation and allow positive round limits')
    if field_credit and any(type(row.fields) is not int or row.fields < 1 for row in (*train, *validation)):
        raise ValueError('Field-aware rows require a positive field count')
    if opening_pair is not None and not isinstance(opening_pair, ProposalPair):
        raise ValueError('A precomputed opening must be a ProposalPair')

    critical = {row.id for row in validation if row.critical}
    families = {row.id: row.family for row in validation}
    family_sizes = Counter(families.values())
    validation_ids = frozenset(families)
    capacities = {row.id: row.fields if field_credit else 0 for row in validation}
    probes = balanced_order(train, seed)
    events = []
    cache = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in cache:
            if len(cache) >= metric_limit:
                raise RuntimeError('Search evaluation budget exhausted')
            observed = evaluate(prompt, row)
            if field_credit and (type(observed.matched_fields) is not int
                                 or not 0 <= observed.matched_fields <= row.fields
                                 or observed.passed != (observed.matched_fields == row.fields)):
                raise ValueError('Field observations must match the row capacity and exact-pass decision')
            cache[key] = observed
        return cache[key]

    def preference(prompt):
        return len(prompt), prompt

    def rank(candidate):
        counts = Counter(families[row_id] for row_id in candidate.passed)
        balance = sum(Fraction(counts[family], size) for family, size in family_sizes.items())
        return (-len(candidate.passed & critical), -balance, -len(candidate.passed),
                -candidate.matched_fields, preference(candidate.prompt))

    def dominates(candidate, possible, fields, prompt):
        return candidate.passed > possible or (candidate.passed == possible
                                               and (-candidate.matched_fields, preference(candidate.prompt))
                                               <= (-fields, preference(prompt)))

    initial_results = [(row, observe(initial, row)) for row in validation]
    archive = [Candidate(initial, frozenset(row.id for row, observed in initial_results if observed.passed),
                         sum(observed.matched_fields for _, observed in initial_results) if field_credit else 0)]
    protected = archive[0].passed & critical
    events.append({'kind': 'validated', 'prompt': initial, 'passed': sorted(archive[0].passed)})
    attempted = {initial}
    exhausted = set()
    cursor = 0
    reflections = 0
    successful_branch = 0
    for round_index in range(rounds):
        if archive[0].passed == validation_ids:
            break
        use_opening = round_index == 0 and opening_pair is not None
        # Reserve the seed-sized validation cost for at least one candidate in this round.
        available_for_probes = metric_limit - len(cache) - len(validation)
        minimum_probes = 0 if use_opening else 1
        if available_for_probes < minimum_probes:
            break
        parent = next((candidate for candidate in archive if candidate.prompt not in exhausted), None)
        if parent is None:
            break
        if use_opening:
            options = opening_pair
        else:
            probe_count = min(train_per_round, len(probes), available_for_probes)
            probes_this_round = [probes[index % len(probes)] for index in range(cursor, cursor + probe_count)]
            cursor += probe_count
            feedback = [(row, observe(parent.prompt, row)) for row in probes_this_round]
            history = [(candidate.prompt, dict(Counter(families[row_id] for row_id in sorted(candidate.passed))))
                       for candidate in archive[:3]]
            options = propose(parent.prompt, feedback, history, proposals_per_round)
            reflections += 1
        if isinstance(options, ProposalPair):
            options = (options.rewrite, options.repair)
        elif isinstance(options, ProposalBatch):
            if options.exhausted:
                exhausted.add(parent.prompt)
            options = options.prompts
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
            fields, available_fields = 0, sum(capacities.values())
            status = 'validated'
            for row in ordered:
                if len(cache) >= round_limit and (prompt, row.id) not in cache:
                    status = 'budget'
                    break
                remaining.remove(row.id)
                available_fields -= capacities[row.id]
                observed = observe(prompt, row)
                if field_credit:
                    fields += observed.matched_fields
                if observed.passed:
                    passed.add(row.id)
                elif adaptive and row.id in protected:
                    status = 'critical_regression'
                    break
                if race and remaining and any(
                    dominates(other, passed | remaining, fields + available_fields, prompt) for other in archive
                ):
                    status = 'dominated'
                    break
            events.append({'kind': status, 'prompt': prompt, 'parent': parent.prompt,
                           'passed': sorted(passed), 'unobserved': sorted(remaining)})
            if status != 'budget':
                attempted.add(prompt)
            if status != 'validated':
                continue
            candidate = Candidate(prompt, frozenset(passed), fields)
            if not any(dominates(other, passed, fields, prompt) for other in archive):
                archive = [other for other in archive
                           if not dominates(candidate, other.passed, other.matched_fields, other.prompt)]
                archive.append(candidate)
                archive.sort(key=rank)
            if archive[0].passed == validation_ids:
                break
            if adaptive and (candidate.passed > parent.passed or
                             candidate.passed == parent.passed and fields > parent.matched_fields):
                successful_branch = branch
                break
    return Result(archive[0].prompt, len(cache), reflections, events)
