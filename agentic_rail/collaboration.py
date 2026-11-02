"""One Rail: collaboration owns integration timing and groups ready development tasks."""
from . import process
from .core import RailError, digest, inside, load_task, read_json, safe_id, timestamp, write_json
import json


def path(root, plan_id):
    return inside(root, f'.rail/collaborations/{safe_id(plan_id)}.json')


def load(root, plan_id):
    plan = read_json(path(root, plan_id))
    if plan.get('version') != 1 or plan.get('id') != plan_id:
        raise RailError('Unsupported collaboration record')
    return plan


def save(root, plan):
    write_json(path(root, plan['id']), plan)
    return plan


def snapshot(root, plan):
    members = {}
    for task_id in plan['members']:
        task = load_task(root, task_id)
        p = process.validate(root, task)
        if p['version'] != 2 or p['stage'] != 'ready' or not p['integration_ready'] or p['review']['state'] != 'approved':
            raise RailError('Member is not PR-approved and integration-ready: ' + task_id)
        if p['integration_mode'] != plan['mode'] or p['batch'] != plan['batch']:
            raise RailError('Member integration mode/batch differs from collaboration: ' + task_id)
        if any(provider not in plan['members'] for provider in p['providers']):
            raise RailError('All provider tasks must be included in the integration plan: ' + task_id)
        # Includes contract, decisions, flow, check/review records and cycle; old evidence
        # cannot survive a changed task even when the operator reuses a revision string.
        members[task_id] = dict(revision=p['revision'], cycle=p['cycle'],
                               sha=digest(json.dumps(task, sort_keys=True, ensure_ascii=False)))
    return members


def current(root, plan):
    members = snapshot(root, plan)
    if not plan['attempts'] or members != plan['attempts'][-1]['members']:
        raise RailError('Integration snapshot is stale; start a new attempt after tasks are ready')
    return plan['attempts'][-1]


def create(root, plan_id, members, mode, batch, owner, trigger, required_checks):
    process.require(owner, trigger, *required_checks)
    if not required_checks:
        raise RailError("Declare required live checks before integration")
    members = list(dict.fromkeys(members))
    if not members or (mode == 'milestone' and not batch.strip()):
        raise RailError('Members and milestone batch required')
    for member in members:
        p = load_task(root, member).get('process', {})
        if p.get('version') != 2 or p['integration_mode'] != mode or p['batch'] != batch:
            raise RailError('Plan members must be v2 tasks with matching integration mode/batch')
    plan = dict(version=1, id=plan_id, owner=owner, members=members, mode=mode,
                batch=batch, trigger=trigger, required_checks=list(dict.fromkeys(required_checks)),
                state='waiting', attempts=[], history=[])
    write_json(path(root, plan_id), plan, exclusive=True)
    return plan


def begin(root, plan_id, actor, evidence, revision, environment, milestone_reached):
    process.require(actor, evidence, revision, environment)
    plan = load(root, plan_id)
    members = snapshot(root, plan)
    if plan['mode'] == 'milestone' and not milestone_reached:
        raise RailError('Explicit --milestone-reached is required; readiness alone does not start integration')
    if plan['attempts']:
        previous = plan['attempts'][-1]
        if plan['state'] in ('running', 'done') and previous['members'] == members:
            raise RailError('Current attempt is running or complete; do not overwrite it')
        for affected in previous.get('affected', []):
            if members[affected]['cycle'] <= previous['members'][affected]['cycle']:
                raise RailError('Failed integration requires rework of affected task: ' + affected)
    attempt = dict(number=len(plan['attempts'])+1, members=members, revision=revision,
        environment=environment, milestone_reached=milestone_reached, actor=actor,
        trigger_evidence=evidence, started_at=timestamp(), checks=[])
    plan['attempts'].append(attempt)
    plan['state'] = 'running'
    return save(root, plan)


def record(root, plan_id, name, result, evidence, actor, affected):
    process.require(name, evidence, actor)
    plan = load(root, plan_id)
    if plan['state'] != 'running':
        raise RailError('Only a running integration accepts live checks')
    attempt = current(root, plan)
    affected = list(dict.fromkeys(affected))
    if any(t not in plan['members'] for t in affected) or (result == 'FAIL' and not affected):
        raise RailError('FAIL requires affected member task IDs')
    if result != 'FAIL' and affected:
        raise RailError('Affected tasks belong to FAIL results')
    attempt['checks'].append(dict(name=name, result=result, kind='live', evidence=evidence,
        actor=actor, affected=affected, at=timestamp()))
    if result == 'FAIL':
        plan['state'] = 'failed'
        attempt['affected'] = affected
    return save(root, plan)


def rework(root, plan_id, task_id, actor, reason):
    plan = load(root, plan_id)
    process.require(actor, reason)
    if plan['state'] != 'failed' or task_id not in plan['attempts'][-1].get('affected', []):
        raise RailError('Only affected tasks from a failed integration can be returned for rework')
    old = plan['attempts'][-1]['members'][task_id]['cycle']
    if load_task(root, task_id)['process']['cycle'] > old:
        raise RailError('Task already returned for rework in this attempt')
    process.rework(root, task_id, 'implement', actor, f"Integration {plan_id}: {reason}")
    plan['history'].append(dict(event='rework', task=task_id, actor=actor, evidence=reason,
                               attempt=plan['attempts'][-1]['number'], at=timestamp()))
    return save(root, plan)


def finish(root, plan_id, actor, evidence, defects, minutes):
    process.require(actor, evidence)
    plan = load(root, plan_id)
    if plan['state'] != 'running' or defects < 0 or minutes < 0:
        raise RailError('Finish requires running integration and nonnegative reflection metrics')
    attempt = current(root, plan)
    latest = {c['name']: c for c in attempt['checks']}
    if (not all(name in latest for name in plan['required_checks'])
            or any(c['result'] != 'PASS' for c in latest.values())):
        raise RailError('All actual integration checks must have latest PASS; Mock cannot complete a plan')
    attempt['reflection'] = dict(actor=actor, evidence=evidence, defects=defects,
                                rework_minutes=minutes, at=timestamp())
    plan['state'] = 'done'
    return save(root, plan)


def status(root, plan_id):
    plan = load(root, plan_id)
    blockers = []
    try:
        members = snapshot(root, plan)
        if plan['attempts'] and members != plan['attempts'][-1]['members']:
            blockers.append('Member snapshots changed; new integration attempt required')
    except RailError as exc:
        blockers.append(str(exc))
    state = plan['state']
    if blockers and state in ('running', 'done'):
        state = 'invalidated'
    return dict(plan, recorded_state=plan['state'], state=state, blockers=blockers,
        integration_complete=state == 'done',
        live_result='NOT_RUN' if not plan['attempts'] else state,
        assurance='Operator-recorded live tests and PR approvals; no GitHub polling, automatic milestone, merge or deployment')


def register(sub):
    commands = sub.add_parser('collaboration', help='Plan and verify integration across development tasks').add_subparsers(dest='collaboration_action', required=True)
    c = commands.add_parser('create')
    c.add_argument('id')
    c.add_argument('--task', action='append', required=True)
    c.add_argument('--check', action='append', required=True, help='Required actual integration check name; repeat for each check')
    c.add_argument('--mode', choices=['milestone', 'per-pr'], default='milestone')
    c.add_argument('--batch', default='')
    c.add_argument('--owner', required=True)
    c.add_argument('--trigger', required=True, help='Agreed milestone criteria or PR integration trigger')
    commands.add_parser('status').add_argument('id')
    for name in ('start', 'record-check', 'rework', 'finish'):
        c = commands.add_parser(name)
        c.add_argument('id')
        c.add_argument('--actor', required=True)
        c.add_argument('--evidence', required=True)
        if name == 'start':
            c.add_argument('--revision', required=True, help='Exact combined integration revision(s)')
            c.add_argument('--environment', required=True, help='Actual integration environment reference')
            c.add_argument('--milestone-reached', action='store_true')
        elif name == 'record-check':
            c.add_argument('--name', required=True)
            c.add_argument('--result', choices=['PASS', 'FAIL', 'NOT_RUN'], required=True)
            c.add_argument('--affected', action='append', default=[])
        elif name == 'rework':
            c.add_argument('--task', required=True)
        else:
            c.add_argument('--defects', type=int, required=True)
            c.add_argument('--rework-minutes', type=int, required=True)


def run(root, a):
    if a.collaboration_action == 'create': return create(root, a.id, a.task, a.mode, a.batch, a.owner, a.trigger, a.check)
    if a.collaboration_action == 'status': return status(root, a.id)
    if a.collaboration_action == 'start': return begin(root, a.id, a.actor, a.evidence, a.revision, a.environment, a.milestone_reached)
    if a.collaboration_action == 'record-check': return record(root, a.id, a.name, a.result, a.evidence, a.actor, a.affected)
    if a.collaboration_action == 'rework': return rework(root, a.id, a.task, a.actor, a.evidence)
    return finish(root, a.id, a.actor, a.evidence, a.defects, a.rework_minutes)
