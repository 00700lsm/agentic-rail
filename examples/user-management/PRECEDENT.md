# User Management example — illustrative, not your accepted project contract

These are sample decisions, not a claim about the current contract repositories.
Copy/adapt into the target project only after checking its accepted decisions.
Scopes below are relative to the directory containing this file.

### DEC-CONTRACT-001 Contract precedes consumer changes
- Scope: backend/*, frontend/*
- Status: active
- Decision: Consumers implement the explicitly pinned, accepted OpenAPI contract version.
- Forbidden: Independently changing an error code or response shape in one consumer.
- Reason: Mock success cannot prove real FE/BE compatibility.

### DEC-CACHE-001 Session isolation
- Scope: frontend/*
- Status: active
- Decision: User-specific cached data is isolated and invalidated on session changes.
- Forbidden: Exposing the previous user's profile after logout or switching accounts.
- Reason: Client cache reuse must not cross user boundaries.
