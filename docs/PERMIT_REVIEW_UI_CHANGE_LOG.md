# Permit Intelligence and Human Review UI changes

## 2026-10-29 — Permit Intelligence first pass

Branch: `qinren/permit-review-ui`.

- Merged the post-analysis Step 1 explanation into the Permit Intelligence heading. The upload state still explains Step 1 before a permit is analyzed.
- Removed the separate document/extraction strip and its nonfunctional View, Download, Print, Copy link, and Open buttons. Kept the current filename as a small identifier beside the heading, and retained a visible warning when extraction is incomplete.
- Put the Human Review progress and its entry button in the heading so the next action stays visible.
- Simplified Key Permit Limits cards. An explicit STOP condition is identified in its title, and a repeated parameter name is removed from the displayed value when present. A card without an explicit STOP label is not presented as one.
- Removed repeated "Source quotation verified" labels. Unverified or unstated source status remains visible per card; original evidence remains available in the condition table and Human Review.
- Removed the nonfunctional "Expand all limits" button.

Verification: Frontend build passed. Focused App and workflow tests passed (17/17). Human Review layout and date auto-fill are not changed in this pass.

## 2026-10-29 — Limit cards and chart density

Branch: `qinren/permit-review-ui`.

- Increased the limit name size, reduced the value size, centered all limit icons, and replaced the decorative wind-gust icon with the standard wind icon. Limit cards and STOP labels now use the PermitPulse blue palette.
- Removed the Permit conditions table from the overview. Its source-verification reminder now links to Human Review, where full conditions and original quotations are available.
- Removed `Permit Conditions by Phase` because it used the exact same phase counts as `Conditions by Phase` in a different chart type.
- Kept three distinct charts—phase, requirement type, and explicit limits—in one desktop row, with responsive wrapping on narrower screens.

Verification: Frontend build passed; focused App and workflow tests passed (17/17).

## 2026-10-29 — Header and permit facts

Branch: `qinren/permit-review-ui`.

- Reduced the top padding above the analyzed Permit Intelligence heading.
- Reordered the six permit facts into two desktop rows of three: permit number, validity and activity first; licensee, issuing authority and total conditions second. Cards are shorter and no longer show redundant decorative icons.
- Kept any geographic restriction as its own card below the six facts.
- Removed the footer disclaimer from this overview and removed the nonfunctional notification and JD profile controls from the header.

Verification: Frontend build passed; focused App and workflow tests passed (18/18).

## 2026-10-29 — Grouped overview and scroll cue

Branch: `qinren/permit-review-ui`.

- Shortened the Permit Intelligence introduction to “Review key permit details and limits here.”
- Grouped the six compact facts under “Basic information” and the three charts under “Condition overview”.
- Added a floating down-arrow while more Permit Intelligence content remains below the viewport; it disappears near the bottom and while another step is active.
- Before/after screenshots were deferred at Qinren's request.

Verification: Frontend build passed; focused App and workflow tests passed (18/18).

## 2026-10-29 — Permit overview navigation and labels

Branch: `qinren/permit-review-ui`.

- Added icons and title-case labels to Basic Information and Condition Overview, matching Key Permit Limits. Removed the redundant extracted-values subtitle.
- Put Key Permit Limits and Condition Overview shortcuts beside the Permit Intelligence heading.
- Gave Basic Information more room on the first desktop screen so Key Permit Limits begins below it.
- Centered the down-arrow at the bottom of the viewport and made it blink; reduced-motion settings disable the animation.
- Made the Human Review actions read “Next: Human Review” and “Next: Open Human Review” for consistent navigation.

Verification: Frontend build passed; focused App and workflow tests passed (18/18).

## 2026-10-29 — Human Review header and progress

Branch: `qinren/permit-review-ui`. Local changes awaiting visual review.

- Stacked Back and Next on the far right of the Step 2 guide.
- Removed the redundant confirmation sentence and replaced the instruction with the requested “Please resolve…” copy.
- Replaced the text progress line with a compact circular dashboard that combines review completion and applicability counts; removed the separate Review progress sidebar.
- Made the Human Review overview card full width and closer to the step guide. Removed its eyebrow, filename/run line, and green review badge.
- Removed two stray literal `n strings that appeared in the review page.

Verification: Frontend build passed; focused App and workflow tests passed (18/18). Older standalone Human Review tests still expect an earlier condition-card layout and need updating separately.

## 2026-10-29 — Human Review typography and applicability ring

Branch: `qinren/permit-review-ui`. Local changes awaiting visual review.

- Matched the Step 2 “Check the interpretation” heading to the Step 1 main heading size and weight.
- Changed the dashboard ring to show Applicable, Not applicable, and Unassessed as green, red, and gray segments. Review completion remains visible as a separate slim bar and count inside the same dashboard.
- Removed the AI extracted interpretation and Effective reviewed interpretation expanders from each condition card. Original document evidence and the full review editor remain available.

Verification: Frontend build passed; focused App and workflow tests passed (18/18).

## 2026-10-29 — Applicability ring correction

Branch: `qinren/permit-review-ui`. Local changes awaiting visual review.

- Removed the blue completion bar from the Human Review dashboard.
- Made the ring show green, red, and gray segments even when a category has zero items; zero-count categories use a small visual marker, while the adjacent numbers remain the true counts.
- Labeled the ring as conditions and the overall progress as review items. The dashboard now identifies location review items separately, explaining why the two totals can differ.

## 2026-10-29 — Consolidated Human Review introduction

Branch: `qinren/permit-review-ui`. Local changes awaiting visual review.

- Updated the Step 2 instruction to: “Please resolve every AI-extracted item to unlock Environmental Intelligence and downstream decision assessment. You can return and edit later.”
- Removed the repeated Human Review heading and explanation below the step guide.
- Moved the review status metrics into the Step 2 guide, alongside the instruction, applicability ring, and navigation controls.
- Renamed the total metric to “Total review items” because it includes the location review item as well as permit conditions.

## 2026-10-29 — Human Review first-screen layout

Branch: `qinren/permit-review-ui`. Local changes awaiting visual review.

- Put Back and Next side by side at the upper right; the Back button now says “Back: Permit Intelligence.”
- Placed the applicability dashboard lower on the left and arranged the six review-status cards in two rows of three on the right.
- Sized the overview frame to fill the initial desktop viewport so the detailed condition list starts below it; narrower screens stack the content for readability.

Verification: Frontend build passed; focused App and workflow tests passed (18/18).

## 2026-10-29 — Focused Human Review workspace

Branch: `qinren/permit-review-ui`. Local changes awaiting visual review.

- Replaced the long stack of repeated condition cards with a compact review queue on the left and one selected item on the right.
- Added search and To check, All, Reviewed, and Source gaps filters so reviewers can find outstanding items quickly.
- Put the original permit wording beside the AI interpretation for the selected item. Kept saved interpretation, evidence routing, and provider details in expandable sections.
- Preserved interpretation correction, applicability, source verification, and bulk actions. Moving between items warns before discarding unsaved edits; saving a resolved item advances to the next unresolved item.
- Updated the frontend tests to reflect the current four-step workflow and focused review layout.

Verification: Frontend build and full test suite passed. Changes remain uncommitted for manual visual review.

## 2026-10-30 — Human Review guidance, duplicate location and multi-select

Branch: `qinren/fixbug-condition34`.

- Linked a structured work location to the permit condition that quotes the same source passage. The location is shown within that condition and no longer appears as a duplicate review item or inflates the review count.
- Preserved valid prior approval/applicability from a former duplicate location item when the linked condition has not yet been reviewed. The reviewed, source-verified point still becomes available to environmental retrieval.
- Added a prominent Human Review instruction below the dashboard, animated downward start cue, and plain-English definitions of Approve and Applicable.
- Added a Multi-select control and Select all visible action to the Review items list. Selected items appear in the existing right-hand detail area, where Bulk Approval and Bulk Applicability can be applied separately.
- Bulk approval remains unavailable for source-unverified, conflicted, already-reviewed, corrected, or Not Applicable items; those cases need individual review.

Verification: Not run in this update; awaiting manual review.

## 2026-10-30 — Permit Intelligence visual corrections

- Restored centered blue Key Permit Limits icons and blue STOP card text to match the PermitPulse palette.
- Added spacing between limit cards and inside the Basic Information group.
- Kept the three Condition Overview charts in one desktop row, with a single-column layout on narrow screens.
- Added scoped styles after the older global stylesheet so these visual rules take effect in the built app.

## 2026-10-29 — Spatial approval unblocks Environmental Intelligence

Branch: `qinren/permit-review-ui`.

- Fixed the location review case where the interpretation was Approved but Applicability remained Unassessed, leaving Step 3 locked.
- Approving a spatial point now also marks that point Applicable for the current assessment; other review items still require their own applicability decision.
- The Human Review guide now identifies whether interpretation approval or applicability is still missing, so the green applicability ring is not mistaken for review completion.
- Updated the current local test run's already approved spatial item to Applicable; its review progress is now 34 of 34 complete.

Verification: Spatial review tests (9/9) and focused frontend tests (21/21) passed.


## 2026-10-30 — Permit typography and combined bulk review

- Repositioned Next: Human Review under the spaced shortcut buttons and removed the inline review count.
- Rendered oxygen as O₂ on one line, enlarged parameter names, reduced value text, darkened headings, and applied the Pulse teal to icons.
- Placed All before To check in the review queue.
- Combined approval and applicability in one aligned form with one Save Selected Reviews action; retained correction values and required Not Applicable justification.
- Frontend production build passed. Focused combined-save checks cover both decisions, preserved corrections and required justification.


## 2026-10-30 — One review readiness dashboard

- Replaced the opening applicability ring with actual review completion: resolved items, remaining items and REVIEW COMPLETE / INCOMPLETE.
- Reused the same reviewSummary readiness calculation previously used in the footer, including interpretation, applicability, conflicts and required justification.
- Removed the separate Review readiness footer.


## 2026-10-30 — Shortcut scroll position

- Measured the running sticky header at approximately 154px, which obscured section headings with the former fixed offsets.
- Both permit shortcuts now measure the current header height on each click and place the section below it with 16px clearance, including after viewport changes.


## 2026-10-30 — Condition 5 source verification

- Reconcile environmental quotations contaminated at their edges by observed repeated page furniture or page-number lines. Remaining wording must still match exactly one physical page.
- Preserve original source spans and persisted analysis; show the verified quotation in Human Review.
- Verified the latest Condition 5 now passes source verification without a new AI request or modifying its saved analysis.
- Validation: 45 targeted backend tests passed, 1 skipped; frontend build passed.


## 2026-10-30 — Skip unresolved sources in bulk review

- Exclude unverified or conflicted rows from bulk writes, list the skipped conditions and reasons, and let eligible rows save. Skipped conditions remain unresolved for individual review.
- Explain all-excluded selections without attempting a request.
- Expanded the opening guidance to the full frame width, reduced row spacing, and centered START REVIEW with three downward arrows on each side.


## 2026-10-30 — Review progress and applicability layout

- Displayed resolved review progress as a horizontal bar, with applicability in a green/red/gray ring and labeled counts below.
- Reduced the right-hand metrics to Pending review, Rejected and Source / review gaps.


## 2026-10-30 — Aligned review overview panels

- Kept applicability in the left panel and moved review progress above the three status cards in a single right panel.
- Aligned both panels and moved Back/Next into a separate row below the full-width title.


## 2026-10-30 — Guided environmental evidence workflow

- Confirm Location & Time now appears first. A unique reviewed, source-verified point and bounded explicit UTC dates are pre-filled; multiple locations and ambiguous/long validity periods require confirmation.
- Confirmation reveals the combined environmental requirements, provider and capability panel. Conditions, source notes, manual FNU inputs and unit details remain available by expansion.
- An explicit Check Connections action probes Open-Meteo metadata and validates configured Copernicus credentials in a bounded subprocess. It does not create environmental evidence or write credentials.
- Fetch is revealed after checking connections. Unavailable sources require acknowledgement as evidence gaps before continuing.
- Editing query inputs invalidates the local confirmation/check and clears displayed results. Existing saved results remain inspectable until edited.
- Removed repeated environmental page headings, document summary and redundant introductory notices; retained mock-mode identification.


## 2026-10-30 — Variable-first requirements panel

- Required environmental variables are now individually visible as expandable rows, grouped beside their corresponding data source and connection status.
- Each variable reveals its units, implementation capability and matching permit conditions, thresholds, source quotations and retrieval notes.
- Removed the separate Required by Permit / Contract and Environmental Capability Coverage sections. Manual FNU inputs remain attached to the relevant turbidity condition.
- Validation: 51 related frontend tests passed; production build passed.


## 2026-10-30 — Compact provider groups and geometry selector

- Moved the opening instruction into the green confirmation note and defaulted editable depth to 0 m.
- Replaced the point-only checkbox with Point / Polygon selection. Polygon is a clearly marked future input and cannot dispatch a point retrieval.
- Confirming the point and UTC period scrolls to the data-source step; removed its redundant introductory sentence.
- Provider information now forms a horizontal header above its variables. Variable names and condition references share a compact line.
- Replaced Not connected badges with actual credential/public API configuration labels; connection checks and their results remain visible.


## 2026-10-30 — Map-based environmental results

- Replaced the default result-card wall with a Leaflet/OpenStreetMap map, a variable selector and a compact source/time/coverage panel.
- Query location and actual provider sample/grid coordinates are drawn separately. Native values and UTC timestamps update when switching variables or already-retrieved times; no provider fetch occurs on selection.
- Missing, masked or rejected values remain unavailable with their actual diagnostic. No passing or area-wide result is inferred from unavailable or point-only data.
- Added validated Polygon/MultiPolygon GeoJSON rendering for structured boundaries; current environmental retrieval remains point-only and does not generate polygon-wide evidence.
- Moved the full existing evidence/provenance/threshold audit into a collapsed Full Evidence & Audit Details section, preserving access to all native points and metadata.
- Added bounded map resizing and cleanup, tile-failure feedback and OpenStreetMap attribution. Installed Leaflet 1.9.4.
- Validation: 76 related frontend tests passed; production build passed. Live map tiles require network access.
