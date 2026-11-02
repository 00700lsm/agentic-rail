import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agentic_rail.cli import main
from agentic_rail.core import load_task
from agentic_rail.install import initialize


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        initialize(self.root)

    def cli(self, *args, ok=True):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['--root', str(self.root), *args])
        if ok: self.assertEqual(code, 0, err.getvalue() + out.getvalue())
        else: self.assertNotEqual(code, 0, out.getvalue())
        return out.getvalue() + err.getvalue()

    def begin(self, name='permission', *extra):
        return self.cli('process', 'start', name, '--goal', name, '--path', name+'.py',
            '--owner', 'developer', '--contract-ref', 'contract@v1',
            '--integration-mode', 'milestone', '--batch', 'M1', *extra)

    def advance(self, stage, name='permission', ok=True):
        return self.cli('process', 'advance', name, '--stage', stage, '--actor', 'developer',
            '--evidence', 'stage artifact', '--revision', name+'@sha1', ok=ok)

    def check(self, kind, name='permission', result='PASS', ok=True):
        return self.cli('task', 'record-check', name, '--kind', kind, '--name', kind,
                        '--result', result, '--evidence', 'test log', ok=ok)

    def verified(self, name='permission'):
        p = load_task(self.root, name)['process']
        if p['stage'] == 'analyze':
            self.advance('analyze', name); self.advance('design', name)
        self.advance('implement', name)
        for kind in ('unit', 'contract', 'mock'): self.check(kind, name)
        self.advance('verify', name)

    def request(self, name='permission', ok=True):
        return self.cli('process', 'request-review', name, '--pr', 'https://github.com/acme/api/pull/1',
                        '--actor', 'developer', '--evidence', 'request URL', ok=ok)

    def approve(self, name='permission', result='approve', actor='reviewer', ok=True):
        return self.cli('process', 'review-result', name, '--result', result, '--actor', actor,
                        '--evidence', 'GitHub review URL', ok=ok)

    def ready(self, name='permission'):
        self.verified(name); self.request(name); self.approve(name); self.advance('review', name)

    def plan(self, members=('permission',), *extra, ok=True):
        args = ['collaboration', 'create', 'M1', '--batch', 'M1', '--owner', 'coordinator',
                '--trigger', 'M1 Auth/User/Permission acceptance checkpoint', '--check', 'G3-G4']
        for member in members: args += ['--task', member]
        return self.cli(*args, *extra, ok=ok)

    def integrate(self, reached=True, ok=True):
        return self.cli('collaboration', 'start', 'M1', '--actor', 'coordinator',
            '--evidence', 'milestone decision', '--revision', 'integration@sha1',
            '--environment', 'local real FE+BE stack',
            *(['--milestone-reached'] if reached else []), ok=ok)

    def live(self, result='PASS', affected=(), ok=True):
        args = ['collaboration', 'record-check', 'M1', '--actor', 'tester', '--evidence', 'live log',
                '--name', 'G3-G4', '--result', result]
        for name in affected: args += ['--affected', name]
        return self.cli(*args, ok=ok)

    def finish(self, ok=True):
        return self.cli('collaboration', 'finish', 'M1', '--actor', 'coordinator',
                        '--evidence', 'reflection', '--defects', '1', '--rework-minutes', '10', ok=ok)

    def state(self):
        return json.loads(self.cli('collaboration', 'status', 'M1'))

    def test_milestone_waits_for_all_approved_tasks_and_explicit_trigger(self):
        self.begin('auth'); self.begin('permission', '--provider', 'auth')
        self.plan(('permission', 'auth'))
        self.ready('permission')
        self.integrate(ok=False)
        self.assertFalse(self.state()['integration_complete'])
        self.ready('auth')
        self.integrate(reached=False, ok=False)
        self.integrate()
        self.finish(ok=False)
        self.live('NOT_RUN'); self.finish(ok=False)
        self.live(); self.finish()
        self.assertTrue(self.state()['integration_complete'])
        # Integration does not assert that GitHub merged anything or close development history.
        self.assertEqual(load_task(self.root, 'permission')['state'], 'ready')
        self.assertIn('reflection', self.state()['attempts'][0])

    def test_mock_is_required_and_never_counts_as_live_integration(self):
        self.begin()
        for stage in ('analyze', 'design', 'implement'): self.advance(stage)
        self.check('unit'); self.check('contract'); self.advance('verify', ok=False)
        self.check('mock', result='NOT_RUN'); self.advance('verify', ok=False)
        self.check('mock'); self.check('integration', ok=False)
        self.advance('verify'); self.request(); self.approve(); self.advance('review')
        self.plan(); self.integrate(); self.finish(ok=False)
        self.cli('task', 'finish', 'permission', ok=False)
        self.advance('integrate', ok=False)

    def test_review_request_changes_requires_rework_and_new_request(self):
        self.begin(); self.verified()
        self.approve(ok=False); self.advance('review', ok=False)
        self.request(); self.approve(actor='DEVELOPER', ok=False)
        self.approve(result='request-changes'); self.advance('review', ok=False)
        self.request(ok=False); self.approve(ok=False)
        self.cli('process', 'rework', 'permission', '--to', 'implement', '--actor', 'developer', '--reason', 'review feedback')
        self.ready()
        self.assertEqual(load_task(self.root, 'permission')['process']['cycle'], 1)

    def test_failed_integration_targets_rework_and_invalidates_old_approval(self):
        self.begin(); self.ready(); self.plan(); self.integrate()
        self.live('FAIL', ok=False)
        self.live('FAIL', ('unknown',), ok=False)
        self.live('FAIL', ('permission',))
        self.finish(ok=False); self.integrate(ok=False)
        self.cli('collaboration', 'rework', 'M1', '--task', 'permission', '--actor', 'coordinator', '--evidence', 'wrong 403')
        p = load_task(self.root, 'permission')['process']
        self.assertFalse(p['integration_ready']); self.assertEqual(p['review']['state'], 'not_requested')
        self.integrate(ok=False)
        self.advance('implement'); self.advance('verify', ok=False)
        for kind in ('unit', 'contract', 'mock'): self.check(kind)
        self.advance('verify'); self.request(); self.approve(); self.advance('review')
        self.integrate(); self.finish(ok=False); self.live(); self.finish()
        self.assertEqual(len(self.state()['attempts']), 2)
        self.assertEqual(self.state()['attempts'][0]['checks'][0]['result'], 'FAIL')

    def test_member_changes_invalidate_completed_or_running_integration(self):
        self.begin(); self.ready(); self.plan(); self.integrate(); self.live(); self.finish()
        self.cli('process', 'rework', 'permission', '--to', 'implement', '--actor', 'developer', '--reason', 'source change')
        self.assertEqual(self.state()['state'], 'invalidated')
        self.assertFalse(self.state()['integration_complete'])
        self.ready(); self.integrate(); self.finish(ok=False)
        self.cli('process', 'rework', 'permission', '--to', 'implement', '--actor', 'developer', '--reason', 'another change')
        self.live(ok=False)

    def test_providers_can_be_parallel_but_must_join_plan(self):
        self.begin('permission', '--provider', 'auth'); self.ready('permission')
        self.plan(); self.integrate(ok=False)
        self.assertIn('provider', self.state()['blockers'][0])

    def test_batch_mismatch_rejected_without_creating_plan(self):
        self.begin()
        self.plan(('permission',), '--batch', 'M2', ok=False)
        self.assertFalse((self.root / '.rail/collaborations/M1.json').exists())

    def test_per_pr_uses_same_live_gate_without_milestone_flag(self):
        self.begin('permission', '--integration-mode', 'per-pr', '--batch', '')
        self.ready()
        self.plan(('permission',), '--mode', 'per-pr', '--batch', '')
        self.integrate(reached=False); self.live(); self.finish()
        self.assertTrue(self.state()['integration_complete'])

    def test_duplicate_plan_and_running_attempt_are_not_overwritten(self):
        self.begin(); self.ready(); self.plan(); self.plan(ok=False)
        self.integrate(); self.integrate(ok=False)
        self.live(); self.finish(); self.integrate(ok=False)
        self.assertEqual(len(self.state()['attempts']), 1)

    def test_ready_task_rejects_new_checks_until_rework(self):
        self.begin(); self.ready()
        self.check('mock', ok=False)
        self.cli('process', 'metric', 'permission', '--defects', '1', '--rework-minutes', '2', '--evidence', 'x', ok=False)

    def test_graph_and_brief_include_collaboration_boundary(self):
        self.begin()
        self.assertIn('contract@v1', self.cli('process', 'brief', 'permission'))
        graph = json.loads(self.cli('process', 'graph', '--format', 'json'))
        self.assertIn({'source':'ready','relation':'joins_plan','target':'integration'}, graph['edges'])
        self.assertIn('live integration NOT_RUN', self.cli('process', 'graph'))

    def test_copied_runtime_executes_new_commands(self):
        self.begin(); self.ready()
        runner = [sys.executable, str(self.root / '.rail/runtime/rail.py'), '--root', str(self.root)]
        result = subprocess.run(runner + ['collaboration', 'create', 'M1', '--task', 'permission',
            '--batch', 'M1', '--owner', 'coordinator', '--trigger', 'M1', '--check', 'G3-G4'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()['live_result'], 'NOT_RUN')
        self.assertIn('.rail/collaborations/', (self.root / '.gitignore').read_text())

    def test_required_checks_cannot_be_replaced_with_unrelated_pass(self):
        self.begin(); self.ready()
        self.plan(('permission',), '--check', 'G4-extra')
        self.integrate(); self.live(); self.finish(ok=False)
        self.cli('collaboration', 'record-check', 'M1', '--name', 'G4-extra', '--result', 'PASS',
                 '--actor', 'tester', '--evidence', 'actual second scenario')
        self.finish()
        self.assertTrue(self.state()['integration_complete'])

    def test_mutual_providers_do_not_deadlock_mock_development(self):
        self.begin('auth', '--provider', 'permission')
        self.begin('permission', '--provider', 'auth')
        self.ready('auth'); self.ready('permission')
        self.plan(('auth', 'permission')); self.integrate(); self.live(); self.finish()
        self.assertTrue(self.state()['integration_complete'])

    def test_blank_and_path_traversal_rejected(self):
        self.begin(); self.ready()
        self.plan(('permission',), '--trigger', ' ', ok=False)
        self.cli('collaboration', 'create', '../escape', '--task', 'permission', '--batch', 'M1',
                 '--owner', 'coordinator', '--trigger', 'M1', '--check', 'G3-G4', ok=False)
        self.plan(); self.integrate()
        self.live('PASS', ('permission',), ok=False)
