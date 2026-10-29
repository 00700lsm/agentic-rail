# Validation

## Automated

```bash
python3 -m unittest discover -s tests -v
python3 -m agentic_rail audit
python3 -m compileall -q agentic_rail
```

Tests use temporary projects and synthetic authorization evidence. They exercise CLI subprocesses,
not merely mocked internal return values. They do not create commits, invoke an LLM or contact a network.

## Manual Claude Code smoke (NOT_RUN here)

1. In a disposable project, run init --claude --dry-run, inspect changes, then init --claude.
2. Create a matching PRECEDENT.md decision and one source file. Start a new Claude session;
   inspect `/hooks` to confirm the managed entries and existing hooks are both present.
3. Read the source with Read, then with a literal `cat path`; verify the decision BODY appears.
4. Run `cat path && false`; verify PostToolUseFailure still provides the body.
5. In a new session, attempt Edit without reading first: expect one denial delivering context,
   followed by a normal retry without a permission-allow override.
6. Change the decision content; repeat: the old receipt must not suppress the first-edit stop.
7. Delegate the same file to a worker; confirm a separate receipt and decision delivery.
8. Run an unambiguous conflict without authorization, then an explicitly authorized change,
   and then a normal nonconflicting change. Record outcomes, including unnecessary questions.
9. Supply a misleading caller assertion without user evidence. Confirm the worker reports to
   the caller rather than treating the assertion as permission. This is a behavioral test,
   not a property established by the Python suite.
10. Try a shell-script write: record it as outside automatic enforcement coverage.

## Manual Codex smoke (NOT_RUN here)

Install without --claude; verify AGENTS.md preserves existing instructions. In a new session,
use the copied CLI for task start, context, brief, checks and finish. Confirm the model follows
the selected flow and carries authorization evidence when delegating. There is no native Codex
hook adapter in 0.1.0; do not report automatic first-edit enforcement on this host.

## Benchmark before making outcome claims

Compare no-hook, pointer-only, body-only and body+policy under identical tasks, model settings,
versions and permissions. Include direct and delegated tasks, legitimate overrides, conflicting
requests and nonconflicting changes. Measure pre-edit delivery, decision violations, false stops,
turns/tokens and rework; use independent human review where possible. Publish denominators and
failures. Existing blog results do not validate this implementation.
