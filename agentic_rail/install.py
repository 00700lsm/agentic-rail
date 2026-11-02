"""Project-local initialization with dry-run, managed markers and legacy-hook cleanup."""
import json
import shutil
from pathlib import Path
from .core import RailError, inside, read_json

BEGIN, END = '<!-- agentic-rail:start -->', '<!-- agentic-rail:end -->'
BLOCK = '''<!-- agentic-rail:start -->
## Agentic Rail
For development, read `.rail/CORE.md` and `.rail/COLLABORATION.md`, then use
`process start` and `process brief` for keyword stages defined in `.rail/process.json`.
Legacy `task start` remains available for existing code/contract/integrate workflows.
Read `python3 .rail/runtime/rail.py task brief <id>`
at task start and pass its output to delegated workers. Use
`python3 .rail/runtime/rail.py context <paths>` when the working scope expands.
Treat PRECEDENT.md as project decisions, subject to higher-priority instructions.
Carry actual user authorization and owned paths through delegation; never invent approval.
Existing explicit user authorization remains valid: do not ask twice.
Record unit/contract/mock checks, then PR request and approval evidence.
For v2, ready tasks join collaboration plans; only live integration completes a plan.
Run task check and relevant tests; distinguish PASS / FAIL / NOT_RUN.
Use process rework after source changes or reconciled decisions; earlier evidence is not reusable.
Keep project PR/review/merge policies. Prefix commit subjects with the actual release version.
<!-- agentic-rail:end -->
'''


def managed(text):
    if BEGIN not in text and END not in text:
        return text.rstrip() + '\n\n' + BLOCK
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
        raise RailError('Malformed agentic-rail markers; repair manually')
    a, b = text.index(BEGIN), text.index(END) + len(END)
    return text[:a] + BLOCK.rstrip() + text[b:]


def initialize(root, claude=False, dry_run=False):
    root = Path(root).resolve()
    assets = Path(__file__).parent / 'assets'
    planned = {}
    def put(path, content, preserve=False):
        target = inside(root, path)
        if not (preserve and target.exists()):
            planned[target] = content
    put('.rail/CORE.md', (assets / 'CORE.md').read_text(encoding='utf-8'), True)
    put('.rail/COLLABORATION.md', (assets / 'COLLABORATION.md').read_text(encoding='utf-8'), True)
    put('.rail/process.json', (assets / 'process.json').read_text(encoding='utf-8'), True)
    for flow in sorted((assets / 'flows').glob('*.md')):
        put('.rail/flows/' + flow.name, flow.read_text(encoding='utf-8'), True)
    for source in Path(__file__).parent.glob('*.py'):
        put('.rail/runtime/agentic_rail/' + source.name, source.read_text(encoding='utf-8'))
    # Assets travel with the runtime so its init --dry-run remains usable.
    for source in sorted(p for p in assets.rglob('*') if p.is_file() and p.suffix in ('.md', '.json')):
        put('.rail/runtime/agentic_rail/assets/' + source.relative_to(assets).as_posix(), source.read_text(encoding='utf-8'))
    put('.rail/runtime/rail.py', 'from agentic_rail.cli import main\nraise SystemExit(main())\n')
    existing_claude = inside(root, 'CLAUDE.md')
    update_claude = claude or (existing_claude.exists() and BEGIN in existing_claude.read_text(encoding='utf-8'))
    for name in ['AGENTS.md'] + (['CLAUDE.md'] if update_claude else []):
        path = inside(root, name)
        put(name, managed(path.read_text(encoding='utf-8') if path.exists() else ''))
    ignore = inside(root, '.gitignore')
    old = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
    missing = [x for x in ('.rail/tasks/', '.rail/state/', '.rail/collaborations/') if x not in old.splitlines()]
    if missing:
        put('.gitignore', old.rstrip() + '\n' + '\n'.join(missing) + '\n')
    path = inside(root, '.claude/settings.json')
    if path.exists():
        config = read_json(path)
        if not isinstance(config, dict) or not isinstance(config.get('hooks', {}), dict):
            raise RailError('Invalid Claude settings shape')
        hooks = config.get('hooks', {})
        removed = False
        command = 'python3 "$CLAUDE_PROJECT_DIR/.rail/runtime/rail.py" --root "$CLAUDE_PROJECT_DIR" hook'
        for name in ('PreToolUse', 'PostToolUse', 'PostToolUseFailure'):
            entries = hooks.get(name, [])
            if not isinstance(entries, list):
                raise RailError(f'Invalid {name} hook list')
            # Remove only our exact command; preserve mixed groups and all other hooks.
            kept = []
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get('hooks'), list):
                    raise RailError(f'Invalid {name} hook entry')
                if any(not isinstance(h, dict) for h in entry['hooks']):
                    raise RailError(f'Invalid {name} hook handler')
                remaining = [h for h in entry['hooks'] if h.get('command') != command]
                if len(remaining) == len(entry['hooks']):
                    kept.append(entry)
                else:
                    removed = True
                    if remaining:
                        kept.append(dict(entry, hooks=remaining))
            if name in hooks:
                hooks[name] = kept
        if removed:
            put('.claude/settings.json', json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    obsolete = inside(root, '.rail/runtime/agentic_rail/hooks.py')
    deleted = [str(obsolete.relative_to(root))] if obsolete.exists() else []
    changed = [str(p.relative_to(root)) for p, content in planned.items()
               if not p.exists() or p.read_text(encoding='utf-8') != content]
    if not dry_run:
        for path, content in planned.items():
            if str(path.relative_to(root)) not in changed:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                backup = inside(root, path.with_name(path.name + '.agentic-rail.bak'))
                if not backup.exists():
                    shutil.copy2(path, backup)
            path.write_text(content, encoding='utf-8')
        if deleted:
            backup = inside(root, obsolete.with_name(obsolete.name + '.agentic-rail.bak'))
            if not backup.exists():
                shutil.copy2(obsolete, backup)
            obsolete.unlink()
    return {'dry_run': dry_run, 'changed': changed, 'deleted': deleted}
