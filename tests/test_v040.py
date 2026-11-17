"""Regression: two-track proof gates and stacked PR preflight against dev."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from agentic_rail.cli import main
from agentic_rail.install import initialize


class V040Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'work'
        self.root.mkdir()
        initialize(self.root)

    def cli(self, *parts, code=0):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(['--root', str(self.root), *parts])
        if code == 0:
            self.assertEqual(result, 0, errors.getvalue() + output.getvalue())
        else:
            self.assertNotEqual(result, 0, output.getvalue())
        return output.getvalue() + errors.getvalue()

    def git(self, *args, cwd=None):
        result = subprocess.run(['git', *args], cwd=cwd or self.root,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def setup_git(self):
        origin = Path(self.tmp.name) / 'remote.git'
        self.git('init', '--bare', str(origin))
        self.git('init')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('checkout', '-b', 'dev')
        (self.root / 'shared.txt').write_text('unchanged\n', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-m', 'bootstrap')
        self.git('remote', 'add', 'origin', str(origin))
        self.git('push', '-u', 'origin', 'dev')
        return origin

    def branch(self, name, parent, filename, content):
        self.git('checkout', '-b', name, parent)
        (self.root / filename).write_text(content, encoding='utf-8')
        self.git('add', filename)
        self.git('commit', '-m', name)
        self.git('push', '-u', 'origin', name)

    def test_proof_gates_block_design_and_verify(self):
        self.cli('process', 'start', 'one', '--goal', 'feature',
                 '--path', 'src/a.py', '--owner', 'worker',
                 '--contract-ref', 'contract@v1', '--integration-mode',
                 'milestone', '--batch', 'M1', '--intensity', '3')
        self.cli('process', 'advance', 'one', '--stage', 'analyze',
                 '--actor', 'worker', '--evidence', 'analyzed')
        self.cli('process', 'advance', 'one', '--stage', 'design',
                 '--actor', 'worker', '--evidence', 'designed', code=2)
        for kind in ('premise', 'invariant', 'deduction', 'counterexample', 'contrapositive'):
            self.cli('process', 'prove', 'one', '--kind', kind,
                     '--result', 'PASS', '--actor', 'worker', '--evidence', kind)
        self.cli('process', 'advance', 'one', '--stage', 'design',
                 '--actor', 'worker', '--evidence', 'designed', code=2)
        self.cli('process', 'prove', 'one', '--kind', 'design-review',
                 '--result', 'PASS', '--actor', 'independent', '--evidence', 'checked')
        self.cli('process', 'advance', 'one', '--stage', 'design',
                 '--actor', 'worker', '--evidence', 'designed')
        self.cli('process', 'advance', 'one', '--stage', 'implement',
                 '--actor', 'worker', '--evidence', 'implemented', '--revision', 'abc123')
        for kind in ('unit', 'contract', 'mock'):
            self.cli('task', 'record-check', 'one', '--kind', kind,
                     '--name', kind, '--result', 'PASS', '--evidence', 'test run')
        self.cli('process', 'advance', 'one', '--stage', 'verify',
                 '--actor', 'worker', '--evidence', 'verified', code=2)
        self.cli('process', 'prove', 'one', '--kind', 'implementation-review',
                 '--result', 'PASS', '--actor', 'independent', '--evidence', 'review')
        self.cli('process', 'advance', 'one', '--stage', 'verify',
                 '--actor', 'worker', '--evidence', 'verified')

    def test_stacked_branches_preflight_dev_without_merge(self):
        self.setup_git()
        self.branch('feature-a', 'dev', 'a.txt', 'a\n')
        self.branch('feature-b', 'feature-a', 'b.txt', 'b\n')
        before_dev = self.git('rev-parse', 'dev')
        result = json.loads(self.cli('collaboration', 'pr-preflight',
            '--branch', 'feature-b', '--branch', 'feature-a',
            '--stack', 'feature-b:feature-a'))
        self.assertEqual(result['status'], 'CLEAN')
        self.assertEqual(result['order'], ['feature-a', 'feature-b'])
        self.assertEqual(result['base'], 'dev')
        self.assertEqual(before_dev, self.git('rev-parse', 'dev'))
        self.branch('feature-c', 'dev', 'shared.txt', 'from C\n')
        self.branch('feature-d', 'dev', 'shared.txt', 'from D\n')
        result = json.loads(self.cli('collaboration', 'pr-preflight',
            '--branch', 'feature-c', '--branch', 'feature-d'))
        self.assertEqual(result['status'], 'CONFLICT')
        self.assertEqual(result['checks'][-1]['branch'], 'feature-d')
        self.assertEqual(before_dev, self.git('rev-parse', 'dev'))

    def test_dev_plan_requires_fresh_preflight(self):
        self.setup_git()
        self.branch('feature-one', 'dev', 'feature.txt', 'feature\n')
        self.cli('process', 'start', 'one', '--goal', 'feature',
                 '--path', 'feature.txt', '--owner', 'worker',
                 '--contract-ref', 'contract@v1',
                 '--integration-mode', 'milestone', '--batch', 'M1')
        for stage in ('analyze', 'design', 'implement'):
            command = ['process', 'advance', 'one', '--stage', stage,
                       '--actor', 'worker', '--evidence', 'done']
            if stage == 'implement':
                command += ['--revision', self.git('rev-parse', 'feature-one')]
            self.cli(*command)
        for kind in ('unit', 'contract', 'mock'):
            self.cli('task', 'record-check', 'one', '--kind', kind,
                     '--name', kind, '--result', 'PASS', '--evidence', 'fixture')
        self.cli('process', 'advance', 'one', '--stage', 'verify', '--actor', 'worker',
                 '--evidence', 'all checks')
        self.cli('process', 'request-review', 'one', '--pr', 'https://example.invalid/pr/1',
                 '--actor', 'worker', '--evidence', 'requested')
        self.cli('process', 'review-result', 'one', '--result', 'approve',
                 '--actor', 'reviewer', '--evidence', 'review')
        self.cli('process', 'advance', 'one', '--stage', 'review',
                 '--actor', 'worker', '--evidence', 'approved')
        self.cli('collaboration', 'create', 'M1', '--task', 'one',
                 '--pr-branch', 'one:feature-one', '--batch', 'M1',
                 '--owner', 'coordinator', '--trigger', 'ready',
                 '--check', 'live')
        start = ('collaboration', 'start', 'M1', '--actor', 'coordinator',
                 '--evidence', 'milestone', '--revision', 'dev@sha',
                 '--environment', 'live', '--milestone-reached')
        self.cli(*start, code=2)
        self.cli('collaboration', 'pr-preflight', '--plan', 'M1',
                 '--branch', 'feature-one')
        self.cli(*start)
        self.assertEqual(self.git('rev-parse', 'dev'), self.git('rev-parse', 'origin/dev'))


if __name__ == '__main__':
    unittest.main()
