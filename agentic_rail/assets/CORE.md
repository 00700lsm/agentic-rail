# Agentic Rail Core

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
