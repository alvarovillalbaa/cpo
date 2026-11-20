"""Use cached validation evidence for native GEPA's supplied opening candidates."""

from benchmarks import grounded


def select_opening(initial, bank, groups, evaluate, *, cap, seed, width, minibatch_size):
    """Run native GEPA over fixed proposals without exposing validation to a proposer.

    GEPA keeps its strict minibatch acceptance and full validation selection.
    Its minibatch and full validation use the same rows. The paid evaluator is
    called once per distinct prompt and case. No new instructions are generated.
    """
    from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, TrackingConfig, optimize_anything
    from gepa.strategies.proposal_sampling import SameParentSampling
    from gepa.utils.stop_condition import ScoreThresholdStopper

    validation = list(groups['validation'])
    candidates = tuple(bank)
    size = len(validation)
    validation_ids = {row['id'] for row in validation}
    if (not candidates or len(set(candidates)) != len(candidates) or initial in candidates or width < 1 or
            len(candidates) % width or len(validation_ids) != size or not 1 <= minibatch_size <= size):
        raise ValueError('Fixed GEPA requires distinct proposals and complete nonempty minibatches')
    if cap < (1 + len(candidates)) * size:
        raise ValueError('The paid cap must cover each distinct supplied prompt on validation')

    fields = len(validation[0]['expected'])
    weight = 1 << (size * fields).bit_length()
    supplied = iter(candidates)
    replies = {}

    def metric(prompt, example):
        row = example['id']
        if row not in validation_ids or prompt not in (initial, *candidates):
            raise ValueError('Fixed GEPA may evaluate only supplied prompts on validation')
        key = prompt, row
        if key not in replies:
            reply = evaluate(prompt, row)
            replies[key] = ((reply.passed * weight + reply.matched_fields) / (weight + fields), {})
        return replies[key]

    def propose(_candidate, _observations, components):
        component, = components
        return {component: next(supplied)}

    config = GEPAConfig(
        engine=EngineConfig(seed=seed, parallel=False, use_cloudpickle=False, cache_evaluation=True,
                            max_candidate_proposals=len(candidates) // width, track_best_outputs=False,
                            sampling_strategy=SameParentSampling(width) if width > 1 else None),
        reflection=ReflectionConfig(reflection_lm=None, custom_candidate_proposer=propose,
                                    reflection_minibatch_size=minibatch_size),
        tracking=TrackingConfig(logger=grounded.GepaLogger()),
        stop_callbacks=ScoreThresholdStopper(1.0),
    )
    return optimize_anything(initial, evaluator=metric, dataset=validation, valset=validation,
                             config=config).best_candidate
