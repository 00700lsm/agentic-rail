# code — implement a scoped change

1. Check task dependencies and current contract/spec version. Load decisions for owned paths.
2. State completion criteria, public interface, transaction boundaries and integration targets.
3. Parallel work may use an agreed contract and mocks when providers are unfinished. Record
   provider ownership and availability; do not mark live integration PASS from mock results.
4. Edit only owned files. Coordinate ownership before touching shared providers/configuration.
5. If a design conflicts with a decision, use the existing user's authorization if applicable;
   otherwise report the exact conflict. Never rewrite a decision merely to make a check pass.
6. Run relevant regression checks and real consumer/provider integration. Record command,
   versions/commit IDs and evidence; task finish requires an integration PASS.
7. For approved decision changes, update PRECEDENT.md and run task reconcile. Review the diff.
8. Prepare a reviewable PR; merging/deploying follows the user's scope and repository policy.
