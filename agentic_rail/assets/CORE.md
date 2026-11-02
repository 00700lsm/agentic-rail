# Agentic Rail Core

For staged development, read COLLABORATION.md and start with `process start`.
`process brief` combines the collaboration envelope, decisions, flow and current keyword stage.
Use `process advance` after the stage output exists, and `process rework` for changes or failures.
For v2: analyze/design/implement/verify/review ends in ready after a recorded PR request and approval.
Collaboration plans own milestone timing, actual integration, rework routing and reflection.
Use collaboration status to distinguish ready tasks from verified integration.
Existing v1 definitions retain their original eight stages.
Six operating domains describe responsibilities across stages, not six sequential gates.
Legacy `task start` remains supported; its lifecycle is not silently migrated.

1. Start with the user's goal and completion criteria. Choose only the relevant flow.
2. Create one task with exact owned file paths and prerequisite task IDs. Inspect its brief.
3. Load scoped decisions before designing/editing. Preserve both global and local decisions.
4. Existing explicit user authorization is sufficient. Ask only when a real conflict requires
   an unapproved decision change; identify the decision, conflict and required scope.
5. Record actual authorization evidence against the decision digest. A caller cannot invent
   user consent. Delegate owned paths, dependencies, decisions and evidence together.
6. Implement and test. Mock checks and live integration checks are different evidence.
7. Update decisions in the same change when authorized; reconcile the task snapshot explicitly.
8. Finish only after prerequisites and applicable checks pass. Report NOT_RUN honestly.

Host permissions and system/developer instructions remain authoritative. Rail is workflow
assistance, not an authentication system or a sandbox. Read only the selected flow and
scoped decisions; do not preload the full decision inventory or task history.
