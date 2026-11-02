# Validation

## Automated

```bash
python3 -m unittest discover -s tests -v
python3 -m agentic_rail audit
python3 -m compileall -q agentic_rail
```

Tests use temporary projects and synthetic authorization evidence. The copied CLI is exercised
as a subprocess, including context, brief, validation and completion. Migration checks cover
legacy hook removal, preservation of unrelated settings and handlers, dry-run and idempotence.

## Manual host smoke (NOT_RUN here)

1. Initialize a disposable project; add --claude only when CLAUDE.md is wanted.
2. Create a scoped PRECEDENT.md decision and start a task for a matching source file.
3. Read task brief and pass the output with the task prompt to the selected model.
4. Confirm decision bodies, owned paths, dependencies and actual approval evidence arrive.
5. Expand the working scope and explicitly read context for the added paths.
6. Run tests and integration, record evidence, then check and finish the task.
7. Repeat with each intended host/model. Do not assume a successful CLI run proves compliance.

## Legacy installation smoke (NOT_RUN in a live host)

Run the updated source CLI init --dry-run against an old installation. Check the planned
settings update and obsolete hooks.py deletion, then run init. Verify only the exact generated
Rail hook command is gone, other handlers remain, and the copied CLI works. Restart the host.
Custom commands must be removed manually. No automatic read-time injection or edit blocking
should remain from Rail. Old receipt files are unused.
## Legacy development process validation (v0.2.0 compatibility)

Run `python3 -m unittest discover -s tests -v`. Process tests cover skipped-stage and legacy-finish
bypasses, stale checks after rework/reconcile, self-review rejection, Mock implementation versus
live integration, deferred providers versus hard dependencies, milestone batches, graph/domain
export, metric corrections and copied-runtime JSON asset installation. Existing task tests
remain unchanged and validate backward compatibility.

These tests use fixture evidence; they do not count as real project integration or LLM compliance.
Host/model dispatch, source revision truth and external GitHub policy remain unverified.

## Collaboration and nested development (v0.3.0)

Tests cover mandatory mock/unit/contract checks, request-before-approval, owner review rejection,
request-changes and fresh approval after rework; all-member readiness and explicit milestone
arrival; missing provider membership, batch mismatch, per-PR alternative; live NOT_RUN/FAIL
blocking; affected-task routing; revision/cycle drift invalidating running/completed integration;
new attempts without stale PASS; duplicate plan protection and copied runtime commands.
The v1 test fixture explicitly installs process-v1.json to protect the previous lifecycle.

All test evidence is synthetic. Actual PoC live service tests and GitHub approvals remain
NOT_RUN by this repository test suite. audit validates PRECEDENT syntax, not all workflow state.
