# Collaboration policy — one Rail, nested development

The project's contract acceptance, ownership, required CI/reviews, merge owner and target
branch policy remain authoritative. Rail records evidence; it does not authenticate it.

1. Agree contract, owners and owned files. Shared code changes need coordination. Use separate
   tasks/worktrees for writers. One writer per task/plan; no distributed locks or cross-machine sync.
2. For process definition v2, each task runs analyze/design/implement/verify/review then ready.
   Record unit, contract and mock PASS for the current cycle/revision. Mock PASS is not live PASS.
3. Request PR approval in GitHub, then record request-review with PR and evidence. Record the
   actual approval or request-changes using review-result. A different actor string is required
   for approval; it is not identity verification or a replacement for required repository reviews.
4. The PoC uses milestone post-integration: create a collaboration plan with members, batch,
   coordinator and agreed trigger. Start only when all members are ready AND the milestone is
   explicitly reached. Readiness alone does not trigger integration. per-pr is also supported.
5. --depends requires a done predecessor (e.g. accepted contract work). --provider allows Mock
   development before the provider is ready. Include all providers in the collaboration plan;
   every included task must be ready. Mutual providers are possible without mutual hard depends.
6. The coordinator gathers exact source revisions in an actual integration environment. Record
   real integration checks with collaboration record-check; NOT_RUN cannot complete a plan.
   Branch collection and PR merge timing follow existing policy; Rail does not merge anything.
7. On FAIL identify affected tasks and evidence. collaboration rework returns each affected task
   to implementation. Re-run checks and request/record fresh approval, then start a new attempt.
   All source changes require process rework, including after a previous integration succeeded.
8. Finish collaboration after live PASS and reflection metrics. Keep failed attempt history.
   ready means development ready; collaboration done means integration verified, not merged/deployed.
9. Version 1 process definitions retain the old eight-stage lifecycle; do not silently replace
   an active project's process.json. New v2 work belongs in a fresh initialized workspace.
10. Commit subjects start with the actual project release version: vX.Y.Z <summary>.

Six operating domains: Governance, Knowledge, Orchestration, Engineering, Quality, Intelligence.
They span both collaboration and development; they are not six sequential steps.
