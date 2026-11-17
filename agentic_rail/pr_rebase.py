"""Git-based PR branch reconciliation for the collaboration track.

Rebase is performed by Git, not by model-generated conflict guesses. This adapter
never creates PRs, approves reviews, or merges into the target branch.
"""
import subprocess
from pathlib import Path
from .core import RailError, inside, load_task, timestamp, write_json, read_json
from . import process


def git(root, *args, check=True):
    try:
        run = subprocess.run(['git', '-C', str(root), *args], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=120, check=False, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RailError(f'Git execution failed: {exc}') from exc
    if check and run.returncode:
        message = (run.stderr or run.stdout).strip()[-1200:]
        raise RailError('git ' + ' '.join(args[:2]) + ': ' + message)
    return run


def state_path(root, task_id):
    return inside(root, '.rail/state/pr-rebase/' + task_id + '.json')


def rebase_active(root):
    for name in ('rebase-merge', 'rebase-apply'):
        rel = git(root, 'rev-parse', '--git-path', name).stdout.strip()
        if Path(rel).is_dir() or (Path(root) / rel).is_dir():
            return True
    return False


def clean(root):
    return not git(root, 'status', '--porcelain', '--untracked-files=no').stdout.strip()


def validate_pr_task(root, task_id):
    task = load_task(root, task_id)
    p = process.validate(root, task)
    if p['version'] != 2 or p['stage'] not in ('review', 'ready'):
        raise RailError('PR rebase requires a version 2 task in review or ready')
    if p['review']['state'] not in ('requested', 'approved', 'changes_requested'):
        raise RailError('A recorded PR request is required before reconciliation')
    return task


def conflict_message(task_id):
    return ('PR rebase has unresolved conflicts for ' + task_id +
            '. Resolve each conflict without discarding either contract, stage with git add, '
            'run relevant tests, then use collaboration pr-rebase ' + task_id +
            ' --continue --actor <actor> --evidence <evidence>; '
            'or use --abort to restore the pre-rebase branch.')


def finish(root, state):
    task_id = state['task']
    if rebase_active(root):
        raise RailError(conflict_message(task_id))
    branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD').stdout.strip()
    if branch != state['branch'] or not clean(root):
        raise RailError('Rebase must finish on the expected clean PR branch')
    after = git(root, 'rev-parse', 'HEAD').stdout.strip()
    before = state['before']
    changed = after != before
    if changed:
        process.rework(root, task_id, 'implement', state['actor'],
                       'PR rebase against ' + state['remote'] + '/' + state['base'] +
                       ': ' + state['evidence'] + ' (old=' + before + ', new=' + after + ')')
    if state['push'] and changed:
        # A lease ensures that another contributor's newer remote tip is not overwritten.
        pushed = git(root, 'push', '--force-with-lease=refs/heads/' + state['branch'] + ':' +
                     state['remote_before'], state['remote'], 'HEAD:refs/heads/' + state['branch'],
                     check=False)
        if pushed.returncode:
            raise RailError('Rebase succeeded locally and previous reviews were invalidated, '
                            'but remote update was rejected; inspect PR branch and retry '
                            'with a fresh lease. ' + (pushed.stderr or pushed.stdout).strip()[-900:])
    return dict(task=task_id, result='REBASED' if changed else 'UP_TO_DATE',
                before=before, after=after,
                pushed=bool(state['push'] and changed),
                required_next='Re-run unit/contract/mock tests and request fresh PR review'
                if changed else 'No history rewrite or review invalidation was required',
                note='No PR merge and no semantic conflict auto-resolution')


def run(root, task_id, branch='', base='main', remote='origin', actor='', evidence='',
        push=False, resume=False, abort=False):
    root = Path(root).resolve()
    process.require(actor, evidence)
    pending = state_path(root, task_id)
    if abort:
        if not pending.is_file() or not rebase_active(root):
            raise RailError('No Rail-managed rebase to abort')
        data = read_json(pending)
        if data['task'] != task_id:
            raise RailError('Rebase task mismatch')
        git(root, 'rebase', '--abort')
        pending.unlink()
        return dict(task=task_id, result='ABORTED', updated=False)
    if resume:
        if not pending.is_file():
            raise RailError('No Rail-managed rebase to continue')
        state = read_json(pending)
        if state['task'] != task_id:
            raise RailError('Rebase task mismatch')
        validate_pr_task(root, task_id)
        if not rebase_active(root):
            raise RailError('No Git rebase in progress; check branch state before retry')
        if git(root, 'ls-files', '-u').stdout.strip():
            raise RailError(conflict_message(task_id))
        if git(root, 'diff', '--check', check=False).returncode:
            raise RailError('Working tree has whitespace errors; fix before continuing')
        result = git(root, '-c', 'core.editor=true', 'rebase', '--continue', check=False)
        if result.returncode or rebase_active(root):
            raise RailError(conflict_message(task_id))
    else:
        if pending.exists() or rebase_active(root):
            raise RailError('Existing rebase detected; continue or abort it first')
        validate_pr_task(root, task_id)
        if not branch or not remote or not base or branch == base:
            raise RailError('Specify a PR branch different from the base')
        for name in (branch, base):
            if git(root, 'check-ref-format', '--branch', name, check=False).returncode:
                raise RailError('Unsafe or invalid Git branch name')
        if git(root, 'check-ref-format', '--allow-onelevel', 'refs/remotes/' + remote,
               check=False).returncode:
            raise RailError('Invalid remote name')
        if git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD').stdout.strip() != branch:
            raise RailError('Check out the exact PR branch before rebasing')
        if not clean(root):
            raise RailError('Commit or stash tracked changes before PR rebase')
        git(root, 'fetch', '--no-tags', remote, base, branch)
        remote_sha = git(root, 'rev-parse', 'refs/remotes/' + remote + '/' + branch).stdout.strip()
        before = git(root, 'rev-parse', 'HEAD').stdout.strip()
        if remote_sha != before:
            raise RailError('Local PR branch does not match remote tip; synchronize first')
        state = dict(task=task_id, branch=branch, base=base, remote=remote,
                     actor=actor, evidence=evidence, push=push, before=before,
                     remote_before=remote_sha, started=timestamp())
        result = git(root, 'rebase', remote + '/' + base, check=False)
        if result.returncode or rebase_active(root):
            if rebase_active(root):
                write_json(pending, state)
                raise RailError(conflict_message(task_id))
            raise RailError('Git rebase failed before entering conflict state: ' +
                            (result.stderr or result.stdout).strip()[-900:])
    # Keep the pending receipt until the Git operation completes; update it only
    # for a rebase that actually entered the conflict-resolution phase.
    try:
        output = finish(root, state)
    finally:
        if pending.is_file() and not rebase_active(root):
            pending.unlink()
    return output
