"""Claude Code adapter: delivery receipts are not proof of compliance or consent."""
import json
import os
import shlex
from pathlib import Path
from .core import RailError, context, digest, inside

EDIT_TOOLS = {'Edit', 'Write', 'MultiEdit'}
EVENTS = {'PreToolUse', 'PostToolUse', 'PostToolUseFailure'}


def extract_paths(root, event):
    data = event.get('tool_input', {})
    if not isinstance(data, dict):
        raise RailError('tool_input must be an object')
    tool = event.get('tool_name')
    if tool in EDIT_TOOLS | {'Read'}:
        value = data.get('file_path')
        if not isinstance(value, str) or not value:
            raise RailError('Missing file_path')
        cwd = inside(root, event.get('cwd', str(root)))
        return [inside(root, cwd / value).relative_to(root).as_posix()]
    if tool == 'Bash':
        # Literal existing operands only. No execution, expansion, or shell write inference.
        command = data.get('command', '')
        if not isinstance(command, str):
            raise RailError('command must be a string')
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:
            return []
        result = []
        cwd = inside(root, event.get('cwd', str(root)))
        for token in tokens:
            if token.startswith('-') or any(x in token for x in ('$', '`', '*', '?', '\n')):
                continue
            try:
                path = inside(root, cwd / token)
            except RailError:
                continue
            if path.is_file() and path.name != 'PRECEDENT.md':
                result.append(path.relative_to(root).as_posix())
        return sorted(set(result))
    return []


def response(event_name, body, deny=None):
    result = dict(hookEventName=event_name, additionalContext=body)
    if deny:
        result.update(permissionDecision='deny', permissionDecisionReason=deny)
    return {'hookSpecificOutput': result}


def handle(root, event):
    root = Path(root).resolve()
    name = event.get('hook_event_name')
    if name not in EVENTS:
        return {}
    editing = name == 'PreToolUse' and event.get('tool_name') in EDIT_TOOLS
    try:
        paths = extract_paths(root, event)
        if not paths:
            return {}
        body, selected = context(root, paths)
        if not body:
            return {}
        # Whole snapshot includes policy; code changes to policy invalidate receipts too.
        identity = json.dumps([event.get('session_id'), event.get('agent_id'), body], ensure_ascii=False)
        receipt = inside(root, '.rail/state/receipts/' + digest(identity))
        known = receipt.exists() and bool(event.get('session_id'))
        if not known:
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.touch(exist_ok=True)
        if editing and not known:
            return response(name, body, 'Decision context delivered. Review it and resolve conflicts before retrying this edit. This is not a request for new user permission.')
        # Re-inject on every matching access: compaction can discard past context.
        return response(name, body)
    except (RailError, OSError, UnicodeError) as exc:
        message = f'agentic-rail could not resolve decision context: {exc}'
        if editing:
            return response(name, message, message)
        return response(name, message + '\nUse the explicit context command before editing; no coverage claimed.')
