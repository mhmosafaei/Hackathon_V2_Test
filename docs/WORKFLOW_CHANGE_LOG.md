# PermitPulse workflow change log

## 2026-10-29 — Human Review and decision flow

**Status:** Implemented locally; awaiting Qinren's manual review. Not committed or pushed.

### User flow

1. Permit Intelligence shows review progress and links conditions to Human Review.
2. Environmental Intelligence relates each permit condition to a variable and provider, and distinguishes configured, retrieved, and unavailable evidence.
3. Human Review stays available and editable at all times. Its readiness summary shows resolved and remaining items.
4. Decision & Work Windows first appears when every review item is resolved. The backend also rejects an assessment request while review is incomplete.
5. Once unlocked, the decision page remains available. Changing a review marks the prior assessment out of date. The page asks for review completion and reevaluation instead of presenting an old WORK result as current.

### Completion rule

At least one review target must exist. Every target must be free of conflicts, have an APPROVED or CORRECTED interpretation, and have APPLICABLE or NOT_APPLICABLE applicability. NOT_APPLICABLE also needs a reviewer justification. This is a human-review workflow state; it does not assert source verification, evidence sufficiency, legal compliance, or permission to work.

### Files changed

- `frontend/src/App.jsx`: review progress, navigation unlock, condition links, stale assessment state.
- `frontend/src/HumanReview.jsx`: matching completion summary and immediate parent updates after review edits.
- `frontend/src/Environmental.jsx`: clearer permit-condition-to-evidence status.
- `frontend/src/DecisionWorkWindows.jsx`: incomplete-review and stale-assessment messages.
- `src/permit/review_overlays.py`: authoritative review progress in review API responses.
- `src/permit/simple_api.py`: decision API rejects incomplete reviews with `HUMAN_REVIEW_INCOMPLETE`.
- Relevant frontend and backend tests updated or added.

### Verification

- Frontend build: passed.
- Frontend `App.test.jsx` and `WorkflowGate.test.jsx`: 15 tests passed.
- Backend `test_review_gate.py`: 2 tests passed, including direct API rejection.
- `git diff --check`: passed.
- Broader async API tests could not finish in this restricted Windows test environment because event-loop initialization blocked in `socketpair`; this is an environment limitation, not a passing test result. Re-run them in the normal development terminal before merging.

### Review notes

- `frontend/package-lock.json` was already modified before this work and was preserved.
- The separate `BUG-001` document-action buttons issue is not changed here.
- No commit or push has been made. Commit to `qinren/update_workflow` only after Qinren reviews the changes.

## 2026-10-29 — Four-step guided navigation

**Status:** Implemented locally for manual review; not committed or pushed.

- Navigation now always shows four numbered steps in the intended order: Permit Intelligence → Human Review → Environmental Intelligence → Decision & Work Windows.
- The next step is disabled until its prerequisite is complete. Permit analysis unlocks Human Review; resolved Human Review unlocks Environmental Intelligence; a returned environmental request or explicit acknowledgement of an evidence gap unlocks Decision & Work Windows.
- Each step has a short explanation at the top, with Back and Next controls. Earlier steps remain available so users can revisit and edit Human Review.
- An evidence gap acknowledgement does not claim evidence was retrieved. The decision may remain UNKNOWN. Backend human-review checks remain in place; the environmental-step acknowledgement is currently a browser workflow state, not a new backend authorization check.
- Reviewed conditions and environmental data remain distinct. Changing a review keeps the prior decision marked out of date until reevaluation.
- Only the app-level navigation and its stylesheet/tests were changed for this iteration; teammate-owned page internals were left alone.
- Frontend build passed; 15 focused frontend tests passed; `git diff --check` passed.

## 2026-10-29 — Review progress synchronization fix

**Status:** Implemented locally; awaiting manual review. Not committed or pushed.

- Fixed a case where Human Review displayed all items resolved while the four-step navigation still showed Environmental Intelligence as locked.
- Human Review now reports its loaded review data to the app-level workflow state. The app also derives review progress from returned review rows when an older running backend response omits `review_progress`.
- The workflow guidance now says "Loading review status" until data is available instead of incorrectly saying all items remain.
- Added a regression test for a failed parent review request followed by a completed review loaded in Human Review.
- 16 focused frontend tests passed. The backend code was not changed in this fix.

## 2026-10-29 — Decision page review-state fix

**Status:** Implemented locally; awaiting manual review. Not committed or pushed.

- Fixed a second review-state mismatch: the navigation could unlock Decision & Work Windows using review rows while the decision page itself still treated Human Review as incomplete because it read only the optional `review_progress` response field.
- Decision now receives the same `reviewComplete` result used by navigation. This lets an already completed review reach the work-window controls.
- Extended the workflow regression test to cover entering Decision after a completed review response without `review_progress`.
- Focused workflow tests passed (2/2), and the frontend build passed.

## 2026-10-29 — Published after user review

- Qinren confirmed the workflow ran successfully and requested submission to her branch.
- Workflow changes were committed as `0bc03be` and pushed to `origin/qinren/update_workflow`.
- The shared base branch was not changed. The existing local `frontend/package-lock.json` modification and `.env` were excluded from the commit.
