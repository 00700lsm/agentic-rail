"""Per-task development inside a collaboration integration plan.

All evidence is an operator record; this module neither sends PR requests nor
queries GitHub. v1 projects retain the old lifecycle without silent migration.
"""
import json
from . import process_v1 as legacy
from .core import RailError, brief, check_task, digest, inside, load_task, start, task_path, timestamp, write_json

STAGES = ('analyze', 'design', 'implement', 'verify', 'review')
DOMAINS = legacy.DOMAINS


def definition(root):
    raw = inside(root, '.rail/process.json').read_text(encoding='utf-8')
    spec = json.loads(raw)
    if spec.get('version') == 1:
        return legacy.definition(root)
    if spec.get('version') != 2 or tuple(s.get('id') for s in spec.get('stages', [])) != STAGES:
        raise RailError('Expected process version 2 and analyze/design/implement/verify/review')
    for s in spec['stages']:
        if (not all(isinstance(s.get(k), str) and s[k].strip() for k in ('goal', 'input', 'output'))
                or not isinstance(s.get('domains'), list) or not s['domains']
                or any(d not in DOMAINS for d in s['domains'])):
            raise RailError('Each stage needs goal/input/output and known operating domains')
    return spec, digest(raw)


def validate(root, task, allow_reconciled=False):
    p = task.get('process', {})
    if p.get('version') == 1:
        return legacy.validate(root, task, allow_reconciled)
    if p.get('version') != 2:
        raise RailError('Not a supported process task')
    _, sha = definition(root)
    if p['definition_sha'] != sha:
        raise RailError('Process definition changed; create a new task')
    errors = check_task(root, task)
    if errors:
        raise RailError('; '.join(errors))
    if not allow_reconciled and p['decisions'] != task['decisions']:
        raise RailError('Decisions reconciled: process rework required')
    return p


def save(root, task):
    write_json(task_path(root, task['id']), task)
    return task


def require(*values):
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise RailError('Actor, evidence and required references must not be empty')


def begin(root, task_id, goal, paths, depends, owner, contract_ref, mode, batch, providers):
    spec, sha = definition(root)
    if spec['version'] == 1:
        return legacy.begin(root, task_id, goal, paths, depends, owner, contract_ref, mode, batch, providers)
    require(owner, contract_ref)
    if mode not in ('milestone', 'per-pr') or (mode == 'milestone' and not batch.strip()):
        raise RailError('Milestone mode requires --batch')
    if task_id in providers:
        raise RailError('A task cannot provide itself')
    # Providers are references, not hard prerequisites: parallel tasks may be created later.
    from .core import safe_id
    for provider in providers:
        safe_id(provider)
    task = start(root, task_id, goal, 'code', paths, depends)
    task['process'] = dict(version=2, definition_sha=sha, stage='analyze', cycle=0,
        owner=owner, contract_ref=contract_ref, integration_mode=mode, batch=batch,
        providers=list(dict.fromkeys(providers)), revision='', history=[], metrics=[],
        implementation_complete=False, integration_ready=False,
        review={'state': 'not_requested'}, decisions=dict(task['decisions']))
    return save(root, task)


def advance(root, task_id, stage, actor, evidence, revision='', pr=''):
    task = load_task(root, task_id)
    p = validate(root, task)
    if p['version'] == 1:
        return legacy.advance(root, task_id, stage, actor, evidence, revision, pr)
    require(actor, evidence)
    if stage not in STAGES or p['stage'] != stage:
        raise RailError('Only the current development stage may advance')
    if stage == 'implement':
        require(revision)
        p['revision'] = revision
    elif stage == 'verify':
        legacy.checks(root, task, ('unit', 'contract', 'mock'))
    elif stage == 'review':
        if p['review']['state'] != 'approved':
            raise RailError('Record a PR approval after request-review before becoming integration-ready')
        p.update(implementation_complete=True, integration_ready=True)
    p['history'].append(dict(event='advance', stage=stage, actor=actor, evidence=evidence,
                             revision=p['revision'], cycle=p['cycle'], at=timestamp()))
    index = STAGES.index(stage)
    p['stage'] = STAGES[index+1] if index+1 < len(STAGES) else 'ready'
    task['state'] = 'ready' if p['stage'] == 'ready' else 'doing'
    return save(root, task)


def review(root, task_id, action, actor, evidence, pr=''):
    task = load_task(root, task_id)
    p = validate(root, task)
    require(actor, evidence)
    if p['version'] != 2 or p['stage'] != 'review':
        raise RailError('PR review actions require a v2 task at review')
    if action == 'request':
        require(pr)
        if p['review']['state'] != 'not_requested':
            raise RailError('Review already requested; source changes require rework')
        p['review'] = dict(state='requested', pr=pr, revision=p['revision'], cycle=p['cycle'],
                           requested_by=actor, requested_at=timestamp(), request_evidence=evidence)
    else:
        if p['review']['state'] != 'requested':
            raise RailError('A pending PR review request is required')
        if actor.strip().casefold() == p['owner'].strip().casefold():
            raise RailError('Reviewer must differ from the implementation owner')
        p['review'].update(state='approved' if action == 'approve' else 'changes_requested',
                           actor=actor, evidence=evidence, at=timestamp())
    p['history'].append(dict(event='review_'+action, actor=actor, evidence=evidence,
                             cycle=p['cycle'], revision=p['revision'], at=timestamp()))
    return save(root, task)


def rework(root, task_id, target, actor, reason):
    task = load_task(root, task_id)
    p = validate(root, task, allow_reconciled=True)
    if p['version'] == 1:
        return legacy.rework(root, task_id, target, actor, reason)
    require(actor, reason)
    if target not in STAGES[:3] or (STAGES + ('ready',)).index(target) > (STAGES + ('ready',)).index(p['stage']):
        raise RailError('Rework must return to an earlier analysis/design/implementation stage')
    p['history'].append(dict(event='rework', stage=p['stage'], target=target, actor=actor,
                             evidence=reason, cycle=p['cycle'], at=timestamp()))
    p['cycle'] += 1
    p.update(stage=target, revision='', implementation_complete=False, integration_ready=False,
             review={'state': 'not_requested'}, decisions=dict(task['decisions']))
    task['state'] = 'doing'
    return save(root, task)


def status(root, task_id):
    task = load_task(root, task_id)
    p = validate(root, task)
    if p['version'] == 1:
        return legacy.status(root, task_id)
    return dict(task=task_id, state=task['state'], **p,
        live_integration='See collaboration status; readiness is not integration success',
        assurance='Operator records only; no GitHub request, authenticated approval, test execution or merge')


def instructions(root, task_id):
    task = load_task(root, task_id)
    p = validate(root, task)
    spec, _ = definition(root)
    stage = next((s for s in spec['stages'] if s['id'] == p['stage']), {'id': p['stage']})
    return brief(root, task_id) + '\n## Development stage\n' + json.dumps(stage, ensure_ascii=False, indent=2)


def graph(root, format='mermaid'):
    spec, _ = definition(root)
    if spec['version'] == 1:
        return legacy.graph(root, format)
    if format == 'json':
        return dict(version=2, nodes=[dict(id=d, type='domain') for d in DOMAINS] +
                    [dict(s, type='stage') for s in spec['stages']] +
                    [dict(id='ready', type='handoff'), dict(id='integration', type='collaboration'),
                     dict(id='reflection', type='collaboration')],
                    edges=[dict(source=a, relation='next', target=b) for a,b in zip(STAGES, STAGES[1:])] +
                    [dict(source=s['id'], relation='serves', target=d) for s in spec['stages'] for d in s['domains']] +
                    [dict(source='review', relation='approved', target='ready'),
                     dict(source='ready', relation='joins_plan', target='integration'),
                     dict(source='integration', relation='rework', target='implement'),
                     dict(source='integration', relation='next', target='reflection')] +
                    [dict(source='integration', relation='serves', target=d) for d in ('governance', 'orchestration', 'quality')] +
                    [dict(source='reflection', relation='serves', target=d) for d in ('knowledge', 'intelligence')])
    return '''flowchart TD
  plan["Collaboration: contract, owners, providers, milestone"] --> analyze
  subgraph development["Per-task development"]
    analyze --> design --> implement --> verify
    verify["unit + contract + mock PASS"] --> review["PR request and approval record"]
    review --> ready["Ready; live integration NOT_RUN"]
  end
  ready --> gate["Collaboration: milestone reached and members ready"]
  gate --> live["Actual integration on pinned revisions"]
  live --> result{PASS?}
  result -->|yes| done["Integration complete; reflection recorded"]
  result -->|no| repair["Affected tasks and reason"]
  repair --> implement'''


def register(sub):
    # Keep v1 arguments available for preserved v1 projects.
    commands = legacy.register(sub)
    for name in ('request-review', 'review-result'):
        s = commands.add_parser(name)
        s.add_argument('id')
        s.add_argument('--actor', required=True)
        s.add_argument('--evidence', required=True)
        if name == 'request-review':
            s.add_argument('--pr', required=True)
        else:
            s.add_argument('--result', choices=['approve', 'request-changes'], required=True)


def run(root, args):
    a = args.process_action
    if a == 'graph': return graph(root, args.format)
    if a == 'start':
        return begin(root, args.id, args.goal, args.path, args.depends, args.owner,
                     args.contract_ref, args.integration_mode, args.batch, args.provider)
    if a == 'status': return status(root, args.id)
    if a == 'brief': return instructions(root, args.id)
    if a == 'advance': return advance(root, args.id, args.stage, args.actor, args.evidence, args.revision, args.pr)
    if a == 'rework': return rework(root, args.id, args.to, args.actor, args.reason)
    if a == 'request-review': return review(root, args.id, 'request', args.actor, args.evidence, args.pr)
    if a == 'review-result': return review(root, args.id, args.result, args.actor, args.evidence)
    if load_task(root, args.id).get('process', {}).get('version') == 2:
        raise RailError('v2 integration metrics belong to collaboration finish')
    return legacy.metric(root, args.id, args.defects, args.rework_minutes, args.evidence)
