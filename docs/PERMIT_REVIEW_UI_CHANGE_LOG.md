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
