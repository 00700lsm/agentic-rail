# Collaboration policy boundary

The existing project's collaboration process remains authoritative. Rail records and
checks local task transitions; it does not change repository permissions or merge policy.

1. Assign an owner and explicit owned files. Agree ownership before shared code changes.
   Use different task IDs and worktrees for parallel writers; no distributed lock is provided.
2. Contract-first: identify the accepted contract commit/reference before development.
   Coordinate contract changes with providers/consumers and update decisions through the
   existing approval process. A nonempty contract reference is not remote acceptance proof.
3. `--depends` means a hard, completed prerequisite. `--provider` means an existing task whose
   completion is required only at integration; implementation may use agreed-contract mocks.
   Do not make mutually dependent integration tasks providers of each other. Shared integration
   can use exact external revisions recorded in evidence instead.
4. Choose `--integration-mode per-pr` or `milestone --batch <name>` explicitly. Both support
   parallel development. Timing is recorded, not scheduled automatically. Temporary integration
   is different from merging a protected branch.
5. Preserve the project's required CI, review count, target branch, contract pin validation,
   merge owner and communication policy. Review in Rail never substitutes for GitHub approval.
   Human/agent reviewers must be separate from the implementation owner; their identities
   are recorded strings, not authenticated permissions.
6. Use the development keywords from process.json. At review completion, implementation may
   be ready while live integration remains pending. The task becomes done only after integration,
   PR handoff and reflection. Done does not mean merged or deployed.
7. Source changes after implementation require `process rework`; use new revision evidence and
   rerun affected checks. After decision approval/reconcile, rework invalidates earlier stages.
8. Record defects, discovery stages and rework time from actual observations. Metrics do not
   establish productivity improvement without a comparison baseline.
9. Commit subject format: `vX.Y.Z <change summary>`. Use the project's actual release version;
   do not copy Rail's version into unrelated projects. Existing repository rules still apply.

Six operating domains (not sequential stages): Governance, Knowledge, Orchestration,
Engineering, Quality, Intelligence. Each stage lists the domains it serves.
