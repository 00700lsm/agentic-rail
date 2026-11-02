"""Explicit development state graph inside the existing collaboration process.

Records are operator assertions, not authenticated approvals or test execution.
The host owns model/tool dispatch; this module owns supported CLI transitions.
"""
import json
from .core import (RailError, brief, check_task, digest, inside, load_task,
                   start, task_path, timestamp, write_json)

STAGES = ('analyze', 'design', 'implement', 'verify', 'review', 'integrate', 'handoff', 'reflect')
DOMAINS = ('governance', 'knowledge', 'orchestration', 'engineering', 'quality', 'intelligence')


def definition(root):
    path = inside(root, '.rail/process.json')
    raw = path.read_text(encoding='utf-8')
    spec = json.loads(raw)
    # The sequence and gates are code-owned. Projects may edit instructions and domains.
    if spec.get('version') != 1 or tuple(s.get('id') for s in spec.get('stages', [])) != STAGES:
        raise RailError('Unsupported process graph: version 1 and the eight ordered stage IDs required')
    for s in spec['stages']:
        if (not all(isinstance(s.get(k), str) and s[k].strip() for k in ('goal', 'input', 'output'))
                or not isinstance(s.get('domains'), list) or not s['domains']
                or any(d not in DOMAINS for d in s['domains'])):
            raise RailError('Each stage needs goal/input/output and known operating domains')
    return spec, digest(raw)


def begin(root, task_id, goal, paths, depends, owner, contract_ref, mode, batch, providers):
    if not owner.strip() or not contract_ref.strip():
        raise RailError('Owner and agreed contract reference are required')
    if mode not in ('per-pr', 'milestone') or (mode == 'milestone' and not batch.strip()):
        raise RailError('Milestone integration requires an explicit batch')
    if task_id in providers:
        raise RailError('A process cannot provide itself')
    for provider in providers:
        load_task(root, provider)
    spec, sha = definition(root)
    task = start(root, task_id, goal, 'code', paths, depends)
    task['process'] = dict(version=1, definition_sha=sha, stage='analyze', cycle=0,
                           owner=owner, contract_ref=contract_ref, integration_mode=mode,
                           batch=batch, providers=providers, revision='', history=[], metrics=[],
                           implementation_complete=False, integration_complete=False,
                           decisions=dict(task['decisions']))
    write_json(task_path(root, task_id), task)
    return task


def validate(root, task, allow_reconciled=False):
    p = task.get('process')
    if not isinstance(p, dict) or p.get('version') != 1:
        raise RailError('Not a version 1 process task; legacy tasks keep their existing lifecycle')
    _, sha = definition(root)
    if p['definition_sha'] != sha:
        raise RailError('Process definition changed: start a new task against the reviewed definition')
    errors = check_task(root, task)
    if errors:
        raise RailError('; '.join(errors))
    if not allow_reconciled and p['decisions'] != task['decisions']:
        raise RailError('Decisions reconciled: use process rework to invalidate previous stage outputs')
    return p


def checks(root, task, kinds):
    p = task['process']
    current = [c for c in task['checks'] if c.get('process_cycle') == p['cycle']
               and c.get('process_stage') == p['stage'] and c.get('revision') == p['revision']]
    latest = {c['name']: c for c in current}
    if not latest or any(c['result'] != 'PASS' for c in latest.values()):
        raise RailError('Current stage checks must all have latest PASS; FAIL/NOT_RUN blocks transition')
    if not all(any(c['kind'] == k for c in latest.values()) for k in kinds):
        raise RailError('Missing current-stage PASS checks: ' + ', '.join(kinds))
    if any(c['decisions'] != task['decisions'] or c['flow_sha'] != task['flow_sha'] for c in latest.values()):
        raise RailError('Checks predate current decisions/flow; rerun them')


def advance(root, task_id, stage, actor, evidence, revision='', pr=''):
    task = load_task(root, task_id)
    p = validate(root, task)
    if task['state'] == 'done' or p['stage'] != stage:
        raise RailError('Only the current stage of an unfinished process can advance')
    if not actor.strip() or not evidence.strip():
        raise RailError('Actor and stage output/evidence are required')
    if stage == 'implement':
        if not revision.strip():
            raise RailError('Implementation requires an exact source revision reference')
        p['revision'] = revision
    elif stage == 'verify':
        checks(root, task, ('unit', 'contract'))
    elif stage == 'review':
        if actor.strip().casefold() == p['owner'].strip().casefold():
            raise RailError('Review must identify a different reviewer/session from the implementation owner')
        p['implementation_complete'] = True
    elif stage == 'integrate':
        for provider in p['providers']:
            dep = load_task(root, provider)
            if dep['state'] != 'done' or check_task(root, dep):
                raise RailError('Integration provider is incomplete or stale: ' + provider)
        checks(root, task, ('integration',))
        p['integration_complete'] = True
    elif stage == 'handoff':
        if not pr.strip():
            raise RailError('Handoff requires a reviewable PR reference; it does not merge the PR')
        p['pr'] = pr
    elif stage == 'reflect':
        if not any(m['cycle'] == p['cycle'] for m in p['metrics']):
            raise RailError('Record measured defects and rework minutes for this cycle before reflection')
    p['history'].append(dict(stage=stage, actor=actor, evidence=evidence, revision=p['revision'],
                             cycle=p['cycle'], at=timestamp(), event='advance'))
    index = STAGES.index(stage)
    p['stage'] = STAGES[index + 1] if index + 1 < len(STAGES) else 'done'
    task['state'] = 'done' if p['stage'] == 'done' else 'doing'
    if task['state'] == 'done':
        task['finished_at'] = timestamp()
    write_json(task_path(root, task_id), task)
    return task


def rework(root, task_id, target, actor, reason):
    task = load_task(root, task_id)
    p = validate(root, task, allow_reconciled=True)
    if task['state'] == 'done':
        raise RailError('Completed process is immutable; start a follow-up task')
    if target not in ('analyze', 'design', 'implement') or STAGES.index(target) > STAGES.index(p['stage']):
        raise RailError('Rework must return to analyze/design/implement at or before the current stage')
    if not actor.strip() or not reason.strip():
        raise RailError('Rework actor and reason are required')
    p['history'].append(dict(event='rework', stage=p['stage'], target=target, actor=actor,
                             evidence=reason, cycle=p['cycle'], at=timestamp()))
    p['cycle'] += 1
    p.update(stage=target, revision='', implementation_complete=False, integration_complete=False)
    p['decisions'] = dict(task['decisions'])
    p.pop('pr', None)
    task['state'] = 'doing'
    write_json(task_path(root, task_id), task)
    return task


def metric(root, task_id, defects, minutes, evidence):
    task = load_task(root, task_id)
    p = validate(root, task)
    if task['state'] == 'done' or defects < 0 or minutes < 0 or not evidence.strip():
        raise RailError('Metrics need an unfinished task, nonnegative values and evidence')
    p['metrics'].append(dict(cycle=p['cycle'], defects=defects, rework_minutes=minutes,
                             evidence=evidence, at=timestamp()))
    write_json(task_path(root, task_id), task)
    return task


def status(root, task_id):
    task = load_task(root, task_id)
    p = validate(root, task)
    latest = {m['cycle']: m for m in p['metrics']}
    return dict(task=task_id, state=task['state'], **p,
                totals=dict(defects=sum(m['defects'] for m in latest.values()),
                            rework_minutes=sum(m['rework_minutes'] for m in latest.values())),
                assurance='Operator records; no model dispatch, authenticated review, CI polling or merge')


def instructions(root, task_id):
    task = load_task(root, task_id)
    p = validate(root, task)
    spec, _ = definition(root)
    stage = next((s for s in spec['stages'] if s['id'] == p['stage']), None)
    return brief(root, task_id) + '\n## Development stage\n' + json.dumps(stage or {'id': 'done'}, ensure_ascii=False, indent=2)


def graph(root, format='mermaid'):
    spec, _ = definition(root)
    if format == 'json':
        return dict(version=1, nodes=[dict(id=d, type='domain') for d in DOMAINS] +
                    [dict(s, type='stage') for s in spec['stages']],
                    edges=[dict(source=a, relation='next', target=b) for a, b in zip(STAGES, STAGES[1:])] +
                    [dict(source=s['id'], relation='serves', target=d) for s in spec['stages'] for d in s['domains']] +
                    [dict(source=a, relation='rework', target=b) for a in STAGES
                     for b in ('analyze', 'design', 'implement') if STAGES.index(b) <= STAGES.index(a)])
    lines = ['flowchart TD', '  collaboration["Collaboration: owner, contract, dependencies, integration timing"] --> analyze']
    for s in spec['stages']:
        lines.append(f'  {s["id"]}["{s["id"]}"]')
    for left, right in zip(STAGES, STAGES[1:]):
        lines.append(f'  {left} --> {right}')
    lines.extend(['  verify -. rework .-> implement', '  review -. rework .-> design',
                  '  integrate -. rework .-> implement', '  reflect --> done["Task done; PR merge is external"]'])
    return '\n'.join(lines)


def register(sub):
    commands = sub.add_parser('process', help='Development stages within collaboration policy').add_subparsers(dest='process_action', required=True)
    commands.add_parser('graph').add_argument('--format', choices=['mermaid', 'json'], default='mermaid')
    s = commands.add_parser('start')
    s.add_argument('id')
    for key in ('goal', 'owner', 'contract-ref'):
        s.add_argument('--' + key, required=True)
    s.add_argument('--path', action='append', required=True)
    s.add_argument('--depends', action='append', default=[])
    s.add_argument('--provider', action='append', default=[])
    s.add_argument('--integration-mode', choices=['per-pr', 'milestone'], required=True)
    s.add_argument('--batch', default='')
    for name in ('status', 'brief'):
        commands.add_parser(name).add_argument('id')
    a = commands.add_parser('advance')
    a.add_argument('id')
    a.add_argument('--stage', choices=STAGES, required=True)
    for key in ('actor', 'evidence'):
        a.add_argument('--' + key, required=True)
    a.add_argument('--revision', default='')
    a.add_argument('--pr', default='')
    r = commands.add_parser('rework')
    r.add_argument('id')
    r.add_argument('--to', choices=['analyze', 'design', 'implement'], required=True)
    r.add_argument('--actor', required=True)
    r.add_argument('--reason', required=True)
    m = commands.add_parser('metric')
    m.add_argument('id')
    m.add_argument('--defects', type=int, required=True)
    m.add_argument('--rework-minutes', type=int, required=True)
    m.add_argument('--evidence', required=True)
    return commands


def run(root, args):
    a = args.process_action
    if a == 'graph':
        return graph(root, args.format)
    if a == 'start':
        return begin(root, args.id, args.goal, args.path, args.depends, args.owner,
                     args.contract_ref, args.integration_mode, args.batch, args.provider)
    if a == 'status':
        return status(root, args.id)
    if a == 'brief':
        return instructions(root, args.id)
    if a == 'advance':
        return advance(root, args.id, args.stage, args.actor, args.evidence, args.revision, args.pr)
    if a == 'rework':
        return rework(root, args.id, args.to, args.actor, args.reason)
    return metric(root, args.id, args.defects, args.rework_minutes, args.evidence)
