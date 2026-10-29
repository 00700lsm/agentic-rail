# contract — agree an interface before consumers depend on it

1. Identify providers, consumers, fields, error codes, authentication and compatibility impact.
2. Read the current authoritative contract and decisions; distinguish proposals from accepted
   decisions. Confirm the relevant decision owner under the project's governance policy.
3. Use existing authorization for an explicit change. Otherwise resolve only the actual conflict.
4. Update schema, rationale and consumer migration plan together. Keep proposal/accepted status
   explicit. Avoid copying the same authoritative definition into each consumer repository.
5. Validate schema and breaking changes; record a contract-kind check with command/evidence.
6. Record the accepted contract commit/version in the handoff. Release consumers only against
   an agreed version. Rail task completion is not a substitute for required PR review/merge.
