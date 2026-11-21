"""Synthetic motor SCM and exact Bayesian inference; no device interfaces."""
import argparse
import itertools
import json
import math
import random
from pathlib import Path

NODES = ('load', 'bearing', 'cooling', 'current', 'temperature', 'vibration')
SENSORS = ('current', 'temperature', 'vibration')
HYPOTHESES = ('load', 'bearing', 'cooling')
VERSION = 'synthetic-motor-v1'


def probability(node, state):
    """Hand-authored CPT; all numbers are teaching assumptions."""
    if node in HYPOTHESES:
        return {'load': .4, 'bearing': .12, 'cooling': .15}[node]
    if node == 'current':
        return .05 + .55 * state['load'] + .25 * state['bearing']
    if node == 'temperature':
        return .05 + .35 * state['load'] + .25 * state['bearing'] + .3 * state['cooling']
    if node == 'vibration':
        return .05 + .7 * state['bearing'] + .1 * state['load']
    raise ValueError('Unknown node')


def validate(values):
    if not isinstance(values, dict) or set(values) - set(NODES):
        raise ValueError('Unknown fields or invalid evidence')
    if any(type(v) is not int or v not in (0, 1) for v in values.values()):
        raise ValueError('Evidence must be binary integers')


def scm(noise, intervention=None):
    """U_i are independent Uniform(0,1); X_i = 1[U_i < CPT_i]."""
    intervention = {} if intervention is None else intervention
    validate(intervention)
    if set(noise) != set(NODES) or any(not 0 <= u < 1 for u in noise.values()):
        raise ValueError('Invalid exogenous variables')
    state = {}
    for node in NODES:
        state[node] = intervention.get(node, int(noise[node] < probability(node, state)))
    return state


def infer(query, evidence=None, intervention=None):
    """Enumerate the truncated factorization, normalizing on observations."""
    if query not in NODES:
        raise ValueError('Unknown query')
    evidence = {} if evidence is None else evidence
    intervention = {} if intervention is None else intervention
    validate(evidence)
    validate(intervention)
    if any(k in evidence and evidence[k] != v for k, v in intervention.items()):
        raise ValueError('Observation contradicts intervention')
    numerator = denominator = 0.0
    for bits in itertools.product((0, 1), repeat=len(NODES)):
        state = dict(zip(NODES, bits))
        if any(state[k] != v for k, v in (evidence | intervention).items()):
            continue
        weight = 1.0
        for node in NODES:
            if node not in intervention:
                p = probability(node, state)
                weight *= p if state[node] else 1 - p
        denominator += weight
        numerator += weight * state[query]
    if not denominator:
        raise ValueError('Impossible evidence')
    return numerator / denominator


def counterfactual_temperature(factual, load):
    """Exact abduction/action/prediction for complete factual observation.

    Conditioning on the factual state truncates U_temperature to an interval.
    The new world keeps that same U, bearing and cooling. No resampling.
    """
    validate(factual)
    if set(factual) != set(NODES) or type(load) is not int or load not in (0, 1):
        raise ValueError('Complete factual state and binary load required')
    p_old = probability('temperature', factual)
    low, high = (0., p_old) if factual['temperature'] else (p_old, 1.)
    p_new = probability('temperature', factual | {'load': load})
    return max(0., min(high, p_new) - low) / (high - low)


def confounding_example():
    """Load confounds fan activation X and overtemperature Y."""
    observed = {}
    intervened = {}
    for fan in (0, 1):
        joint = marginal = causal = 0.
        for load in (0, 1):
            p_load = .5
            p_fan = .9 if load else .1
            assignment = p_fan if fan else 1 - p_fan
            p_hot = (.8 if load else .2) - .1 * fan
            joint += p_load * assignment * p_hot
            marginal += p_load * assignment
            causal += p_load * p_hot
        observed[str(fan)] = joint / marginal
        intervened[str(fan)] = causal
    return {'observational': observed, 'interventional': intervened,
            'assumptions': 'Synthetic known load confounder, positivity, consistency, no other confounders'}


class ReadOnlyTools:
    def __init__(self, records):
        self.records = records
        self.audit = []

    def call(self, name, arguments):
        if name != 'read_synthetic_evidence' or arguments != {}:
            raise PermissionError('Only the parameter-free synthetic evidence reader is allowed')
        self.audit.append({'tool': name, 'category': 'observation', 'synthetic': True})
        return [dict(record) for record in self.records]


def diagnose(tools):
    """Scripted agent: collect, validate, infer, suggest; never execute actions."""
    records = tools.call('read_synthetic_evidence', {})
    evidence, conflicts = {}, []
    for row in records:
        if set(row) != {'field', 'value', 'source'} or not isinstance(row['source'], str) or not row['source']:
            raise ValueError('Malformed evidence record')
        validate({row['field']: row['value']})
        key, value = row['field'], row['value']
        if key in evidence and evidence[key] != value:
            conflicts.append(key)
        evidence[key] = value
    if conflicts:
        return {'status': 'conflicting_evidence', 'conflicts': sorted(set(conflicts)),
                'hypotheses': [], 'records': records, 'category': 'observation',
                'recommendation': 'Reconcile sources and timestamps before inference'}
    hypotheses = []
    for h in HYPOTHESES:
        support, against, neutral = [], [], []
        for key, value in evidence.items():
            single = infer(h, {key: value})
            delta = single - infer(h)
            item = {'field': key, 'value': value, 'single_evidence_delta': delta}
            (support if delta > 1e-10 else against if delta < -1e-10 else neutral).append(item)
        posterior = infer(h, evidence)
        hypotheses.append({'hypothesis': h, 'prior': infer(h), 'posterior': posterior,
                           'support': support, 'against': against, 'neutral': neutral,
                           'missing': sorted(set(NODES) - set(evidence)),
                           'uncertainty_bits': -sum(p * math.log2(p) for p in (posterior, 1-posterior) if p),
                           'category': 'observation'})
    return {'status': 'insufficient_evidence' if not evidence else 'hypotheses_only',
            'model': VERSION, 'synthetic': True, 'records': records, 'hypotheses': hypotheses,
            'root_cause_confirmed': False,
            'uncertainty': 'CPT, graph direction and omitted causes are assumed; entropy excludes model error',
            'suggestions': [
                {'category': 'observation', 'text': 'Request existing load, cooling and maintenance logs'},
                {'category': 'intervention_proposal_only', 'text': 'Qualified staff may design an isolated load experiment after separate safety review; no execution'}],
            'audit': tools.audit}


def generate(seed, size):
    rng = random.Random(seed)
    return [dict(id=f'{seed}-{i}', **scm({n: rng.random() for n in NODES})) for i in range(size)]


def score(rows, shrink):
    pairs = []
    for row in rows:
        raw = infer('bearing', {n: row[n] for n in SENSORS})
        pairs.append(((1-shrink)*raw + shrink*.12, row['bearing']))
    bins = []
    for lower in (0., .2, .4, .6, .8):
        selected = [(p, y) for p, y in pairs if lower <= p < lower+.2]
        bins.append({'lower': lower, 'count': len(selected),
                     'mean_prediction': sum(p for p, _ in selected)/len(selected) if selected else None,
                     'frequency': sum(y for _, y in selected)/len(selected) if selected else None})
    return {'brier': sum((p-y)**2 for p, y in pairs)/len(pairs), 'reliability_bins': bins}


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    calibration, test = generate(2201, 1000), generate(2202, 1000)
    candidates = {str(s): score(calibration, s)['brier'] for s in (0., .25, .5, .75, 1.)}
    chosen = float(min(candidates, key=candidates.get))
    noise = dict(zip(NODES, (.2, .05, .8, .4, .4, .2)))
    factual = scm(noise)
    report = {'model': VERSION, 'confounding': confounding_example(),
              'counterfactual': {'noise': noise, 'factual': factual, 'same_noise_do_load_0': scm(noise, {'load': 0}),
                                 'conditional_hot_probability': counterfactual_temperature(factual, 0)},
              'diagnosis': diagnose(ReadOnlyTools([{'field': n, 'value': factual[n], 'source': 'synthetic-case-1'} for n in SENSORS])),
              'calibration': {'seed': 2201, 'count': len(calibration), 'candidate_brier': candidates, 'chosen_shrink': chosen},
              'test': {'seed': 2202, 'count': len(test), 'raw': score(test, 0), 'frozen_calibrated': score(test, chosen)},
              'limits': 'Synthetic same-generator calibration only; not real failure probability or external validation'}
    for name, value in [('report.json', report), ('calibration.json', calibration), ('test.json', test)]:
        (output / name).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'output': output.name, 'chosen_shrink': chosen, 'test_brier': report['test']['frozen_calibrated']['brier']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
