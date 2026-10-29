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
