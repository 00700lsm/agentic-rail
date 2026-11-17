"""Optional, fail-closed, recorded proof gates for version 2 development tasks.

These are operator assertions with explicit evidence, not executed tests or authenticated identities.
Existing v0.3 tasks with no assurance policy preserve their prior lifecycle.
"""
from .core import RailError, timestamp

PROOFS = ('premise', 'invariant', 'deduction', 'counterexample', 'contrapositive')
KINDS = PROOFS + ('design-review', 'implementation-review')
MODES = ('off', 'auto', 'mass')


def configure(intensity, delegation):
    if intensity not in (1, 2, 3):
        raise RailError('Intensity must be 1, 2, or 3')
    if delegation not in MODES:
        raise RailError('Delegation must be off, auto, or mass')
    return dict(intensity=intensity, delegation=delegation, proofs=[])


def record(task, kind, result, actor, evidence):
    policy = task.get('process', {}).get('assurance')
    if not policy:
        raise RailError('Assurance is not enabled on this task (start with --intensity)')
    if kind not in KINDS or result not in ('PASS', 'FAIL', 'NOT_RUN'):
        raise RailError('Invalid proof kind or outcome')
    if not actor.strip() or not evidence.strip():
        raise RailError('Proof actor and evidence are required')
    stage = task['process']['stage']
    if kind == 'design-review':
        if stage != 'design':
            raise RailError('Design review must be recorded before leaving design')
    elif kind == 'implementation-review':
        if stage != 'verify':
            raise RailError('Implementation review must be recorded at verify')
    elif stage != 'design':
        raise RailError('Logical proof must be recorded during design')
    if kind.endswith('-review') and actor.casefold().strip() == task['process']['owner'].casefold().strip():
        raise RailError('Independent reviewer must differ from the owner')
    policy['proofs'].append(dict(kind=kind, result=result, actor=actor, evidence=evidence,
        cycle=task['process']['cycle'], revision=task['process']['revision'] if kind == 'implementation-review' else '',
        decisions=dict(task['decisions']), contract_ref=task['process']['contract_ref'], at=timestamp()))
    return policy


def evaluate(task, stage):
    p = task.get('process', {})
    policy = p.get('assurance')
    if not policy:
        return dict(enabled=False, status='LEGACY', missing=[], blocking=[])
    level = policy['intensity']
    required = []
    if stage == 'design' and level >= 2:
        required.extend(PROOFS)
        if level == 3 or policy['delegation'] == 'mass':
            required.append('design-review')
    if stage == 'verify' and level >= 2:
        required.append('implementation-review')
    latest = {}
    for proof in policy.get('proofs', []):
        if (proof.get('cycle') == p['cycle'] and proof.get('decisions') == task['decisions']
                and proof.get('contract_ref') == p['contract_ref']
                and (proof['kind'] != 'implementation-review' or proof.get('revision') == p['revision'])):
            latest[proof['kind']] = proof
    missing = [kind for kind in required if kind not in latest]
    blocking = [kind for kind in required if kind in latest and latest[kind]['result'] != 'PASS']
    return dict(enabled=True, intensity=level, delegation=policy['delegation'],
                stage=stage, status='PASS' if not missing and not blocking else 'BLOCKED',
                missing=missing, blocking=blocking,
                note='Evidence is operator-recorded, not automatically executed or authenticated')


def require_gate(task, stage):
    result = evaluate(task, stage)
    if result['status'] == 'BLOCKED':
        raise RailError('Assurance gate blocked at ' + stage + ': missing=' +
                        ','.join(result['missing']) + '; non-PASS=' + ','.join(result['blocking']))


def brief_policy(task):
    p = task.get('process', {})
    policy = p.get('assurance')
    if not policy:
        return 'Assurance: legacy lifecycle (no proof gate).'
    return ('Assurance: intensity=' + str(policy['intensity']) + ', delegation=' + policy['delegation'] +
            '. Proofs are recorded evidence, not executable formal proofs. '
            'Delegation setting is advisory and does not invoke workers or install hooks.')
