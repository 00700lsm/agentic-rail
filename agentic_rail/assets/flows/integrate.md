# integrate — make independently developed parts work together

Choose integration timing explicitly. Neither option is inherently a defect:
- Per-PR integration: merge prerequisites, update branches, verify the combined result each PR.
- Milestone integration: build independently against agreed contracts, then integrate a batch.

1. Record exact contract/FE/BE revisions, provider/consumer ordering and batch boundary.
2. Use separate worktrees/branches and explicit file ownership for parallel development.
3. Check predecessor tasks. An unavailable provider can justify mocks, but leaves live checks
   NOT_RUN and the integration task incomplete. Create a separate implementation task if needed.
4. Run real auth/session, permission, success/error, persistence and cross-module scenarios
   relevant to this change. Distinguish test failures from unavailable infrastructure.
5. Compare implementation and contract; amend through its decision process, not a local patch
   that silently changes the shared interface.
6. Record defects, discovery stage, affected PRs and rework time for timing comparisons.
7. Finish only after actual integration PASS; carry residual risks and revision IDs into review.
