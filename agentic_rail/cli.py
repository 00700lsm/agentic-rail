import argparse
import json
import sys
from pathlib import Path
from . import __version__
from .core import (RailError, approve, brief, check_task, context, decisions, load_task,
                   reconcile, start, task_path, timestamp, write_json)
from .hooks import handle
from .install import initialize


def parser():
    p = argparse.ArgumentParser(prog='agentic-rail')
    p.add_argument('--root', default='.', help='Project root (before subcommand)')
    p.add_argument('--version', action='version', version=__version__)
    sub = p.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--claude', action='store_true')
    init.add_argument('--dry-run', action='store_true')
    c = sub.add_parser('context')
    c.add_argument('paths', nargs='+')
    c.add_argument('--budget', type=int, default=8000, help='UTF-8 byte limit; never silently truncates')
    sub.add_parser('audit')
    sub.add_parser('hook', help='Read a Claude Code hook event from stdin')
    task = sub.add_parser('task').add_subparsers(dest='action', required=True)
    s = task.add_parser('start')
    s.add_argument('id')
    s.add_argument('--goal', required=True)
    s.add_argument('--flow', required=True, choices=['code', 'contract', 'integrate'])
    s.add_argument('--path', action='append', required=True)
    s.add_argument('--depends', action='append', default=[])
    for name in ('brief', 'check', 'reconcile', 'finish'):
        task.add_parser(name).add_argument('id')
    a = task.add_parser('approve')
    a.add_argument('id')
    for name in ('decision', 'quote', 'source', 'change'):
        a.add_argument('--' + name, required=True)
    record = task.add_parser('record-check')
    record.add_argument('id')
    record.add_argument('--name', required=True)
    record.add_argument('--kind', choices=['unit', 'contract', 'integration', 'other'], required=True)
    record.add_argument('--result', choices=['PASS', 'FAIL', 'NOT_RUN'], required=True)
    record.add_argument('--evidence', required=True)
    return p


def run(args):
    root = Path(args.root).resolve()
    if args.command == 'init':
        return initialize(root, args.claude, args.dry_run), 0
    if args.command == 'context':
        body, _ = context(root, args.paths, args.budget)
        return body or 'No active decision matched. This does not mean the project has no constraints.', 0
    if args.command == 'audit':
        records = decisions(root)
        return {'status': 'PASS', 'decisions': len(records), 'active': sum(d.status == 'active' for d in records)}, 0
    if args.command == 'hook':
        raw = sys.stdin.read(1000001)
        if len(raw) > 1000000:
            raise RailError('Hook input too large')
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise RailError('Hook input must be an object')
        return handle(root, event), 0
    action = args.action
    if action == 'start':
        return start(root, args.id, args.goal, args.flow, args.path, args.depends), 0
    if action == 'approve':
        return approve(root, args.id, args.decision, args.quote, args.source, args.change), 0
    if action == 'brief':
        return brief(root, args.id), 0
    if action == 'reconcile':
        return reconcile(root, args.id), 0
    task = load_task(root, args.id)
    if action == 'record-check':
        if task['state'] == 'done':
            raise RailError('Completed tasks are immutable')
        if not args.name.strip() or not args.evidence.strip():
            raise RailError('Check name and evidence must not be empty')
        task['checks'].append(dict(name=args.name, kind=args.kind, result=args.result,
                                   evidence=args.evidence, recorded_at=timestamp(),
                                   decisions=task['decisions'], flow_sha=task['flow_sha']))
        task['state'] = 'doing'
        write_json(task_path(root, args.id), task)
        return task, 0
    errors = check_task(root, task)
    if action == 'finish':
        # Preserve history; latest observation of a named check is authoritative.
        checks = {c['name']: c for c in task['checks']}
        if not checks or any(c['result'] != 'PASS' for c in checks.values()):
            errors.append('All recorded checks must have a latest PASS; FAIL/NOT_RUN cannot mean done')
        if any(c.get('decisions') != task['decisions'] or c.get('flow_sha') != task['flow_sha']
               for c in checks.values()):
            errors.append('Checks predate the current decision/flow snapshot; rerun and record them')
        needed = 'contract' if task['flow'] == 'contract' else 'integration'
        if not any(c['kind'] == needed and c['result'] == 'PASS' for c in checks.values()):
            errors.append(f'A PASS {needed} check is required for this flow')
        if not errors:
            task['state'] = 'done'
            task['finished_at'] = timestamp()
            write_json(task_path(root, args.id), task)
    return {'task': args.id, 'status': 'FAIL' if errors else 'PASS', 'errors': errors}, 1 if errors else 0


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        value, code = run(args)
        print(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
        return code
    except (RailError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'agentic-rail: {exc}', file=sys.stderr)
        # Claude PreToolUse interprets exit 2 as a blocking failure. Other commands also fail visibly.
        return 2
