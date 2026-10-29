import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from agentic_rail.core import (RailError, approve, brief, check_task, context, decisions,
                               load_task, reconcile, select, start, task_path, write_json)
from agentic_rail.hooks import handle
from agentic_rail.install import initialize
from agentic_rail.cli import main


def record(key='DEC-001', scope='src/*', decision='Keep the existing response shape.'):
    return (f'### {key} Response contract\n- Scope: {scope}\n- Status: active\n'
            f'- Decision: {decision}\n- Forbidden: Silently changing the response.\n'
            '- Reason: Consumers depend on this shape.\n')


class RailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'src').mkdir()
        (self.root / 'src/a.py').write_text('pass\n')
        (self.root / 'PRECEDENT.md').write_text(record(), encoding='utf-8')

    def event(self, name='PostToolUse', tool='Read', agent='one', **kwargs):
        return dict(hook_event_name=name, tool_name=tool, session_id='session', agent_id=agent,
                    tool_input=kwargs or {'file_path': str(self.root / 'src/a.py')})

    def init(self):
        initialize(self.root)

    def task(self, name='one', deps=None):
        return start(self.root, name, 'Test response', 'code', ['src/a.py'], deps or [])

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['--root', str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def test_scoped_body(self):
        body, items = context(self.root, ['src/a.py'])
        self.assertIn('Forbidden: Silently', body)
        self.assertEqual([d.id for d in items], ['DEC-001'])
        self.assertEqual(select(self.root, ['other.py']), [])

    def test_global_and_local_accumulate(self):
        (self.root / 'src/PRECEDENT.md').write_text(record('DEC-002', '*.py'))
        self.assertEqual({d.id for d in select(self.root, ['src/a.py'])}, {'DEC-001', 'DEC-002'})

    def test_duplicate_ids_rejected(self):
        (self.root / 'src/PRECEDENT.md').write_text(record())
        with self.assertRaises(RailError):
            decisions(self.root)

    def test_malformed_record(self):
        (self.root / 'PRECEDENT.md').write_text('### DEC-001 Broken\n')
        with self.assertRaises(RailError):
            decisions(self.root)

    def test_retired_omitted(self):
        (self.root / 'PRECEDENT.md').write_text(record().replace('Status: active', 'Status: retired'))
        self.assertEqual(select(self.root, ['src/a.py']), [])

    def test_budget_no_partial_prohibition(self):
        with self.assertRaises(RailError):
            context(self.root, ['src/a.py'], 20)

    def test_unicode_byte_budget(self):
        (self.root / 'PRECEDENT.md').write_text(record(decision='한글' * 3000), encoding='utf-8')
        with self.assertRaises(RailError):
            context(self.root, ['src/a.py'])

    def test_traversal_rejected(self):
        with self.assertRaises(RailError):
            context(self.root, ['../outside'])

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / 'src/link').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RailError):
                context(self.root, ['src/link/file'])

    def test_code_fence_heading_is_not_decision(self):
        (self.root / 'PRECEDENT.md').write_text(record() + '\n```md\n### Fake heading\n```\n')
        self.assertEqual(len(decisions(self.root)), 1)

    def test_first_edit_denied_then_retry_without_allow(self):
        event = self.event('PreToolUse', 'Edit')
        first = handle(self.root, event)['hookSpecificOutput']
        second = handle(self.root, event)['hookSpecificOutput']
        self.assertEqual(first['permissionDecision'], 'deny')
        self.assertNotIn('permissionDecision', second)

    def test_read_receipt_and_agent_isolation(self):
        handle(self.root, self.event())
        self.assertNotIn('permissionDecision', handle(self.root, self.event('PreToolUse', 'Write'))['hookSpecificOutput'])
        self.assertEqual(handle(self.root, self.event('PreToolUse', 'Write', 'two'))['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_decision_revision_invalidates_receipt(self):
        handle(self.root, self.event())
        (self.root / 'PRECEDENT.md').write_text(record(decision='A new response shape.'))
        self.assertEqual(handle(self.root, self.event('PreToolUse', 'Edit'))['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_compaction_reinjects_body(self):
        one = handle(self.root, self.event())
        self.assertEqual(handle(self.root, self.event()), one)

    def test_failed_shell_read_context(self):
        event = self.event('PostToolUseFailure', 'Bash', command=f'cat "{self.root}/src/a.py" && false')
        self.assertIn('DEC-001', handle(self.root, event)['hookSpecificOutput']['additionalContext'])

    def test_shell_not_executed(self):
        event = self.event(tool='Bash', command='touch SENTINEL; cat src/a.py')
        handle(self.root, event)
        self.assertFalse((self.root / 'SENTINEL').exists())

    def test_invalid_context_blocks_edit(self):
        (self.root / 'PRECEDENT.md').write_text('invalid')
        self.assertEqual(handle(self.root, self.event('PreToolUse', 'Edit'))['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_dry_run_writes_nothing(self):
        result = initialize(self.root, claude=True, dry_run=True)
        self.assertTrue(result['changed'])
        self.assertFalse((self.root / '.rail').exists())
        self.assertFalse((self.root / 'AGENTS.md').exists())

    def test_init_preserves_user_hooks_and_idempotent(self):
        (self.root / '.claude').mkdir()
        custom = {'matcher': 'Read', 'hooks': [{'type': 'command', 'command': 'echo custom'}]}
        (self.root / '.claude/settings.json').write_text(json.dumps({'env': {'CUSTOM': 'yes'}, 'hooks': {'PostToolUse': [custom]}}))
        (self.root / 'AGENTS.md').write_text('My project rules\n')
        initialize(self.root, claude=True)
        self.assertEqual(initialize(self.root, claude=True)['changed'], [])
        settings = json.loads((self.root / '.claude/settings.json').read_text())
        self.assertIn(custom, settings['hooks']['PostToolUse'])
        self.assertEqual(settings['env'], {'CUSTOM': 'yes'})
        self.assertTrue((self.root / 'AGENTS.md').read_text().startswith('My project rules'))

    def test_init_preserves_custom_flow(self):
        self.init()
        (self.root / '.rail/flows/code.md').write_text('Custom code flow')
        self.init()
        self.assertEqual((self.root / '.rail/flows/code.md').read_text(), 'Custom code flow')

    def test_init_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / '.rail').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RailError):
                initialize(self.root)
            self.assertFalse(list(Path(outside).iterdir()))

    def test_dependency_blocks_brief(self):
        self.init()
        self.task('provider')
        self.task('consumer', ['provider'])
        with self.assertRaises(RailError):
            brief(self.root, 'consumer')

    def test_snapshot_drift_and_authorized_reconcile(self):
        self.init()
        self.task()
        approve(self.root, 'one', 'DEC-001', 'Change response shape to v2', 'conversation:1', 'v2 response')
        (self.root / 'PRECEDENT.md').write_text(record(decision='Use v2 response.'))
        self.assertTrue(check_task(self.root, load_task(self.root, 'one')))
        task = reconcile(self.root, 'one')
        self.assertEqual(check_task(self.root, task), [])
        self.assertNotEqual(task['approvals'][0]['sha'], task['decisions']['DEC-001'])
        (self.root / 'PRECEDENT.md').write_text(record(decision='Unapproved v3 response.'))
        with self.assertRaises(RailError):
            reconcile(self.root, 'one')

    def test_unauthorized_reconcile_rejected(self):
        self.init()
        self.task()
        (self.root / 'PRECEDENT.md').write_text(record(decision='Changed'))
        with self.assertRaises(RailError):
            reconcile(self.root, 'one')

    def test_stale_approval_rejected(self):
        self.init()
        self.task()
        (self.root / 'PRECEDENT.md').write_text(record(decision='Changed'))
        with self.assertRaises(RailError):
            approve(self.root, 'one', 'DEC-001', 'yes', 'chat:1', 'change')

    def test_brief_contains_exact_evidence(self):
        self.init()
        self.task()
        approve(self.root, 'one', 'DEC-001', 'v2로 변경 승인', 'chat:42', 'v2')
        output = brief(self.root, 'one')
        self.assertIn('v2로 변경 승인', output)
        self.assertIn('chat:42', output)
        self.assertIn('src/a.py', output)

    def test_flow_drift(self):
        self.init()
        task = self.task()
        (self.root / '.rail/flows/code.md').write_text('Changed flow')
        self.assertTrue(check_task(self.root, task))

    def test_task_id_traversal(self):
        self.init()
        with self.assertRaises(RailError):
            self.task('../escape')

    def test_duplicate_task_not_overwritten(self):
        self.init()
        self.task()
        with self.assertRaises(FileExistsError):
            self.task()

    def test_not_run_is_not_done(self):
        self.init()
        self.task()
        self.cli('task', 'record-check', 'one', '--name', 'live', '--kind', 'integration', '--result', 'NOT_RUN', '--evidence', 'Backend unavailable')
        self.assertEqual(self.cli('task', 'finish', 'one')[0], 1)
        self.cli('task', 'record-check', 'one', '--name', 'live', '--kind', 'integration', '--result', 'PASS', '--evidence', 'Live log at /tmp/test.log')
        self.assertEqual(self.cli('task', 'finish', 'one')[0], 0)

    def test_mock_only_cannot_finish_code_task(self):
        self.init()
        self.task()
        self.cli('task', 'record-check', 'one', '--name', 'mock', '--kind', 'unit', '--result', 'PASS', '--evidence', 'mock results')
        self.assertEqual(self.cli('task', 'finish', 'one')[0], 1)

    def test_relative_read_uses_event_cwd(self):
        event = self.event(file_path='a.py')
        event['cwd'] = str(self.root / 'src')
        self.assertIn('DEC-001', handle(self.root, event)['hookSpecificOutput']['additionalContext'])

    def test_checks_invalid_after_reconcile(self):
        self.init()
        self.task()
        self.cli('task', 'record-check', 'one', '--name', 'live', '--kind', 'integration', '--result', 'PASS', '--evidence', 'old run')
        approve(self.root, 'one', 'DEC-001', 'Change', 'chat:1', 'new response')
        (self.root / 'PRECEDENT.md').write_text(record(decision='New response'))
        reconcile(self.root, 'one')
        self.assertEqual(self.cli('task', 'finish', 'one')[0], 1)

    def test_completed_dependency_unblocks_consumer(self):
        self.init()
        self.task('provider')
        self.task('consumer', ['provider'])
        self.cli('task', 'record-check', 'provider', '--name', 'live', '--kind', 'integration', '--result', 'PASS', '--evidence', 'provider run')
        self.assertEqual(self.cli('task', 'finish', 'provider')[0], 0)
        self.assertIn('Dependencies: provider', brief(self.root, 'consumer'))

    def test_copied_runtime_cli_lifecycle(self):
        initialize(self.root, claude=True)
        runner = [sys.executable, str(self.root / '.rail/runtime/rail.py'), '--root', str(self.root)]
        def run(*args, data=None):
            result = subprocess.run(runner + list(args), input=data, text=True, capture_output=True, cwd=self.root)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout
        run('audit')
        run('task', 'start', 'live', '--flow', 'code', '--goal', 'CLI smoke', '--path', 'src/a.py')
        self.assertIn('DEC-001', run('task', 'brief', 'live'))
        result = json.loads(run('hook', data=json.dumps(self.event())))
        self.assertEqual(result['hookSpecificOutput']['hookEventName'], 'PostToolUse')
        run('task', 'record-check', 'live', '--name', 'smoke', '--kind', 'integration', '--result', 'PASS', '--evidence', 'CLI subprocess fixture')
        run('task', 'finish', 'live')
        self.assertEqual(load_task(self.root, 'live')['state'], 'done')

if __name__ == '__main__':
    unittest.main()
