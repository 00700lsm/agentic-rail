import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agentic_rail.cli import main
from agentic_rail.core import approve, load_task, reconcile, start
from agentic_rail.install import initialize
from agentic_rail.process import STAGES, DOMAINS


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        initialize(self.root)

    def cli(self, *args, ok=True):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['--root', str(self.root), *args])
        if ok:
            self.assertEqual(code, 0, err.getvalue() + out.getvalue())
        else:
            self.assertNotEqual(code, 0, out.getvalue())
        return out.getvalue() + err.getvalue()

    def begin(self, *extra):
        return self.cli('process', 'start', 'feature', '--goal', 'Permission API',
                        '--path', 'src/permission.py', '--owner', 'worker-A',
                        '--contract-ref', 'contract@abc123', '--integration-mode', 'per-pr', *extra)

    def advance(self, stage, *extra, ok=True):
        actor = 'reviewer-B' if stage == 'review' else 'worker-A'
        return self.cli('process', 'advance', 'feature', '--stage', stage,
                        '--actor', actor, '--evidence', 'fixture evidence', *extra, ok=ok)

    def check(self, kind, result='PASS', name=None):
        return self.cli('task', 'record-check', 'feature', '--kind', kind,
                        '--name', name or kind, '--result', result, '--evidence', 'fixture log')

    def implement(self):
        self.advance('analyze')
        self.advance('design')
        self.advance('implement', '--revision', 'backend@def456/frontend@fed321')

    def review(self):
        self.check('unit')
        self.check('contract')
        self.advance('verify')
        self.advance('review')

    def test_no_skip_or_legacy_finish_bypass(self):
        self.begin()
        self.advance('review', ok=False)
        self.cli('task', 'record-check', 'feature', '--kind', 'integration', '--name', 'early', '--result', 'PASS', '--evidence', 'early', ok=False)
        self.cli('task', 'finish', 'feature', ok=False)
        self.assertEqual(load_task(self.root, 'feature')['process']['stage'], 'analyze')

    def test_mock_implementation_and_live_completion_are_separate(self):
        self.begin()
        self.implement()
        self.review()
        p = load_task(self.root, 'feature')['process']
        self.assertTrue(p['implementation_complete'])
        self.assertFalse(p['integration_complete'])
        self.check('integration', 'NOT_RUN')
        self.advance('integrate', ok=False)
        self.check('integration')
        self.advance('integrate')
        self.advance('handoff', ok=False)
        self.advance('handoff', '--pr', 'https://github.com/example/project/pull/1')
        self.advance('reflect', ok=False)
        self.cli('process', 'metric', 'feature', '--defects', '1', '--rework-minutes', '12', '--evidence', 'time log')
        self.advance('reflect')
        task = load_task(self.root, 'feature')
        self.assertEqual(task['state'], 'done')
        self.assertEqual([h['stage'] for h in task['process']['history']], list(STAGES))
        self.cli('process', 'rework', 'feature', '--to', 'implement', '--actor', 'worker-A', '--reason', 'change', ok=False)
        self.check_done_rejected()

    def check_done_rejected(self):
        self.cli('task', 'record-check', 'feature', '--kind', 'unit', '--name', 'later', '--result', 'PASS', '--evidence', 'later', ok=False)

    def test_local_verification_requires_contract_and_latest_pass(self):
        self.begin()
        self.implement()
        self.check('unit')
        self.advance('verify', ok=False)
        self.check('contract')
        self.check('unit', 'FAIL')
        self.advance('verify', ok=False)
        self.check('unit')
        self.advance('verify')
        self.advance('review', '--actor', 'WORKER-A', ok=False)
        self.advance('review')

    def test_rework_invalidates_checks_and_completion_flags(self):
        self.begin()
        self.implement()
        self.review()
        self.check('integration')
        self.advance('integrate')
        self.cli('process', 'rework', 'feature', '--to', 'implement', '--actor', 'worker-A', '--reason', 'source changed')
        self.advance('implement', '--revision', 'new-source')
        self.advance('verify', ok=False)
        p = load_task(self.root, 'feature')['process']
        self.assertFalse(p['implementation_complete'])
        self.assertFalse(p['integration_complete'])
        self.assertEqual(p['cycle'], 1)
        self.review()
        self.advance('integrate', ok=False)

    def test_provider_blocks_integration_not_mock_implementation(self):
        start(self.root, 'provider', 'Auth', 'code', ['src/auth.py'], [])
        self.begin('--provider', 'provider')
        self.implement()
        self.review()
        self.check('integration')
        self.advance('integrate', ok=False)
        self.cli('task', 'record-check', 'provider', '--kind', 'integration', '--name', 'auth', '--result', 'PASS', '--evidence', 'fixture')
        self.cli('task', 'finish', 'provider')
        self.advance('integrate')

    def test_hard_dependency_blocks_brief_and_stages(self):
        start(self.root, 'contract', 'Contract', 'contract', ['api.yaml'], [])
        self.begin('--depends', 'contract')
        self.cli('process', 'brief', 'feature', ok=False)
        self.advance('analyze', ok=False)

    def test_milestone_requires_batch_and_carries_collaboration_context(self):
        self.cli('process', 'start', 'bad', '--goal', 'x', '--path', 'x', '--owner', 'a',
                 '--contract-ref', 'abc', '--integration-mode', 'milestone', ok=False)
        self.assertFalse((self.root / '.rail/tasks/bad.json').exists())
        self.begin('--integration-mode', 'milestone', '--batch', 'M1')
        brief = self.cli('process', 'brief', 'feature')
        for term in ('M1', 'contract@abc123', 'worker-A', 'analyze', 'governance'):
            self.assertIn(term, brief)

    def test_graph_represents_stages_domains_and_rework(self):
        g = json.loads(self.cli('process', 'graph', '--format', 'json'))
        self.assertEqual({n['id'] for n in g['nodes'] if n['type'] == 'domain'}, set(DOMAINS))
        self.assertEqual([n['id'] for n in g['nodes'] if n['type'] == 'stage'], list(STAGES))
        self.assertIn({'source': 'integrate', 'relation': 'rework', 'target': 'implement'}, g['edges'])
        self.assertIn('verify --> review', self.cli('process', 'graph'))

    def test_definition_drift_and_invalid_stage_order(self):
        self.begin()
        path = self.root / '.rail/process.json'
        data = json.loads(path.read_text())
        data['stages'][0]['goal'] = 'changed'
        path.write_text(json.dumps(data))
        self.advance('analyze', ok=False)
        data['stages'].reverse()
        path.write_text(json.dumps(data))
        self.cli('process', 'graph', ok=False)

    def test_reconcile_requires_rework_before_reusing_stage_results(self):
        path = self.root / 'PRECEDENT.md'
        path.write_text('### DEC-1 Contract\n- Scope: src/*\n- Status: active\n- Decision: v1\n- Forbidden: drift\n- Reason: compatibility\n')
        self.begin()
        self.implement()
        self.review()
        approve(self.root, 'feature', 'DEC-1', 'Use v2', 'chat:1', 'v2')
        path.write_text(path.read_text().replace('Decision: v1', 'Decision: v2'))
        reconcile(self.root, 'feature')
        self.advance('integrate', ok=False)
        self.cli('process', 'rework', 'feature', '--to', 'design', '--actor', 'worker-A', '--reason', 'decision changed')
        self.advance('design')
        self.advance('implement', '--revision', 'v2-source')
        self.advance('verify', ok=False)

    def test_metrics_replace_latest_cycle_measurement_not_double_count(self):
        self.begin()
        for defects in ('1', '2'):
            self.cli('process', 'metric', 'feature', '--defects', defects, '--rework-minutes', '5', '--evidence', 'measurement')
        status = json.loads(self.cli('process', 'status', 'feature'))
        self.assertEqual(status['totals'], {'defects': 2, 'rework_minutes': 5})
        self.cli('process', 'metric', 'feature', '--defects', '-1', '--rework-minutes', '5', '--evidence', 'bad', ok=False)

    def test_copied_runtime_and_preserved_project_definition(self):
        path = self.root / '.rail/process.json'
        data = json.loads(path.read_text())
        data['stages'][0]['goal'] = 'Project-specific analysis'
        path.write_text(json.dumps(data))
        self.assertEqual(initialize(self.root)['changed'], [])
        runner = [sys.executable, str(self.root / '.rail/runtime/rail.py'), '--root', str(self.root)]
        result = subprocess.run(runner + ['process', 'graph', '--format', 'json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Project-specific analysis', result.stdout)
        # The copied runtime carries JSON assets and can initialize another project.
        with tempfile.TemporaryDirectory() as fresh:
            result = subprocess.run([sys.executable, str(self.root / '.rail/runtime/rail.py'), '--root', fresh, 'init'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(fresh) / '.rail/process.json').exists())


if __name__ == '__main__':
    unittest.main()
