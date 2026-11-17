"""Non-mutating multi-PR preflight, including dependent/stacked branches.

Git's merge-tree checks the *cumulative* tree, not isolated PR-to-main diffs.
Synthetic commits are written only to Git's object database; no refs, index,
working files, PRs, or protected branches are modified. Git >= 2.38 required.
"""
import os
import re
import subprocess
from pathlib import Path
from .core import RailError

SAFE_REMOTE = re.compile(r"^[A-Za-z0-9_.-]+$")


def git(root, *args, check=True, env=None):
    try:
        proc = subprocess.run(
            ['git', '-C', str(root), *args], encoding='utf-8',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            stdin=subprocess.DEVNULL, timeout=120, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RailError('Git preflight unavailable: ' + str(exc)) from exc
    if check and proc.returncode:
        raise RailError('git ' + ' '.join(args[:2]) + ': ' +
                        (proc.stderr or proc.stdout).strip()[-1500:])
    return proc


def branch_name(root, name):
    if (not name or name.startswith('-') or
        git(root, 'check-ref-format', '--branch', name, check=False).returncode):
        raise RailError('Invalid branch: ' + str(name))
    return name


def order_branches(branches, parents):
    # Topological order, stable in the command-line order for unrelated PRs.
    pending = list(branches)
    ordered = []
    while pending:
        ready = [b for b in pending if b not in parents or parents[b] in ordered]
        if not ready:
            raise RailError('Stack dependency cycle or missing parent: ' + ', '.join(pending))
        ordered.extend(ready)
        pending = [b for b in pending if b not in ready]
    return ordered


def preflight(root, branches, stacks=(), base='main', remote='origin'):
    root = Path(root).resolve()
    branch_name(root, base)
    if not remote or not SAFE_REMOTE.fullmatch(remote) or remote in ('.', '..'):
        raise RailError('Invalid Git remote')
    if not branches or len(set(branches)) != len(branches):
        raise RailError('Provide distinct --branch values')
    for name in branches:
        branch_name(root, name)
        if name == base:
            raise RailError('A PR cannot target itself')
    parents = {}
    for spec in stacks:
        if ':' not in spec:
            raise RailError('Stack must be CHILD:PARENT')
        child, parent = spec.split(':', 1)
        if child not in branches or (parent not in branches and parent != base):
            raise RailError('Stack endpoints must be listed PR branches or base')
        if child in parents or child == parent:
            raise RailError('Duplicate/self stack relation: ' + spec)
        parents[child] = parent
    ordered = order_branches(branches, parents)

    help_output = git(root, 'merge-tree', '-h', check=False)
    if '--write-tree' not in (help_output.stdout + help_output.stderr):
        raise RailError('Git merge-tree --write-tree is required (Git 2.38+)')
    for name in [base] + ordered:
        git(root, 'fetch', '--no-tags', remote,
            '+refs/heads/' + name + ':refs/remotes/' + remote + '/' + name)

    def remote_sha(branch):
        return git(root, 'rev-parse', '--verify', 'refs/remotes/' +
                   remote + '/' + branch + '^{commit}').stdout.strip()

    commit = remote_sha(base)
    refs = {branch: remote_sha(branch) for branch in ordered}
    report = []
    env = os.environ.copy()
    env.update(GIT_AUTHOR_NAME='Agentic Rail', GIT_AUTHOR_EMAIL='rail@invalid.local',
               GIT_COMMITTER_NAME='Agentic Rail', GIT_COMMITTER_EMAIL='rail@invalid.local')
    for branch in ordered:
        head = refs[branch]
        parent = parents.get(branch)
        if parent and parent != base:
            relation = git(root, 'merge-base', '--is-ancestor', refs[parent], head,
                           check=False).returncode
            if relation == 1:
                report.append(dict(branch=branch, parent=parent, status='OUTDATED_STACK',
                                   reason='PR head does not contain declared parent tip; restack and retest'))
                return dict(status='BLOCKED', base=base, remote=remote,
                            order=ordered, checks=report, mutated_refs=False,
                            note='No source files, refs or PRs were changed')
            if relation:
                raise RailError('Cannot inspect stack ancestry')
        # 0 clean, 1 textual conflict, >=2 command error (Git convention).
        merged = git(root, 'merge-tree', '--write-tree', commit, head, check=False)
        if merged.returncode == 1:
            report.append(dict(branch=branch, parent=parent or base,
                               status='CONFLICT',
                               details=(merged.stdout + '\n' + merged.stderr)[-3000:]))
            return dict(status='CONFLICT', base=base, remote=remote,
                        order=ordered, checks=report, mutated_refs=False,
                        note='A cumulative trial merge failed; resolve/restack then rerun')
        if merged.returncode:
            raise RailError('merge-tree failed: ' + (merged.stderr or merged.stdout)[-1200:])
        tree = merged.stdout.splitlines()[0].strip()
        if not re.fullmatch('[a-f0-9]{40,64}', tree):
            raise RailError('merge-tree did not return a valid tree object')
        # Simulate the effect of accepting this PR so the next PR is compared
        # against ALL preceding PRs. commit-tree writes an unreachable Git object,
        # not an actual Git branch or merge.
        result = git(root, 'commit-tree', tree, '-p', commit, '-p', head, env=env)
        commit = result.stdout.strip()
        report.append(dict(branch=branch, parent=parent or base,
                           status='CLEAN', source_commit=head))
    return dict(status='CLEAN', base=base, remote=remote, order=ordered,
                checks=report, mutated_refs=False,
                note='Git textual merge only; contract/runtime integration tests remain required')
