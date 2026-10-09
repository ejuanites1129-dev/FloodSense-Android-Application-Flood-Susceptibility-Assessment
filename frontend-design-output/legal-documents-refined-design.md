# FloodSense legal document screen concepts

Created: 6 October 2026
Generation mode: built-in ImageGen
Purpose: visual refinement of the existing Flutter Terms of Use and Privacy Policy screens.

## Deliverables

- [Terms of Use](terms-of-use-refined-mobile.png)
- [Privacy Policy](privacy-policy-refined-mobile.png)

Images are kept at their native generated resolution. Portrait composition is designed for a viewport around 390 × 844 logical pixels.

## Design decisions

- Very pale blue page background and a compact document metadata header.
- A single white accordion panel with fine separators rather than a stack of heavily elevated cards.
- Small numbered section markers for scan order, semibold titles, and quieter helper text.
- Existing individual accordion controls, Expand all, Collapse all, and Back to onboarding retained.
- Fixed footer with adequate scroll clearance; it is not a draggable sheet.
- No extra setup steps or review-completion actions.

## Implementation boundary

These are visual concepts, not a change to legal content, publication status, consent behavior, or the application's setup gates. Use the actual loaded document title, version, section order, section summaries, and full body text. The images illustrate the first eight visible sections from the supplied screenshots; additional sections remain reachable through scrolling. The displayed prototype draft label must follow the actual document status. Section numbers identify positions, not review completion. Flutter should allow wrapping, text scaling, and accessible touch targets rather than shrinking long text to match the raster.

## Terms of Use generation prompt

```text
Use case: ui-mockup
Asset type: one high-fidelity Flutter Android Terms of Use screen; portrait proportions equivalent to 390 by 844 logical pixels.

Reference image 1 is the current FloodSense Terms of Use screen. Reference image 2 is the current Privacy Policy companion. Use them for the exact accordion interaction, section titles, and brand context. Redesign the presentation with restrained polish. This is a visual redesign of the document page, not a new legal policy or onboarding workflow.

Style:
A very pale blue background #F1F8FC covers the entire screen, with a barely perceptible light-blue gradient. White reading surfaces, FloodSense blue #1A94D5 only for accents and actions, dark navy headings, secondary slate text. Crisp contemporary sans-serif. Spacious alignment without large empty gaps. NO maps, contour patterns, illustrations, huge hero, glossy 3D, saturated full-screen blue, heavy shadows, or multicolored badges.

Layout:
Simple Android status bar.
App bar: back arrow and "Terms of Use".
Below it a compact pale-blue document header, about 80 logical pixels high, with a small blue outline document icon in a 36px pale-blue circle. Text "FloodSense" as a small eyebrow, a small neutral "Prototype draft" badge, and "Version prototype-draft-1". One line "Tap a section to read its details." Avoid repeating the long document title.
Next a slim toolbar: "Document sections" left aligned; two small accessible text controls "Expand all" and "Collapse all", arranged beneath or beside the heading with ample space. Do not render as tabs or onboarding steps.

One continuous white rounded accordion panel with a very fine border, subtle horizontal dividers, and clear 16px padding; replace the stack of bulky shadowed cards. Each row contains a small pale-blue rounded square with a blue section number, then title in semibold 15–16px, helper text in 12–13px slate, and a down chevron anchored at the right. Every row is individually expandable. Allow long titles to wrap naturally. Keep all sections in the scrollable list; the view is a viewport, not the complete policy.

Render these rows verbatim, in order:
01 "Purpose and research scope" / "What FloodSense is"
02 "Eligibility and account responsibility" / "Who may create and use an account"
03 "Acceptable use" / "Use the prototype responsibly"
04 "Prohibited use" / "Activities the service does not permit"
05 "Scenario-based and non-real-time limitations" / "Scenarios are hypothetical"
06 "No official forecast, warning, or evacuation order" / "Outputs are decision-support information"
07 "Reliance on official authorities" / "Official instructions take priority"
08 "Third-party services and links" / "External services have separate terms"

Sticky bottom navigation surface: white with a thin divider, safe-area padding, and one full-width pale-blue outlined button with a left arrow and exact text "Back to onboarding". This footer is fixed, NOT draggable; no drag handle. Leave content clearance above it. Show natural scroll continuation if necessary rather than shrinking text to fit.

Preserve Expand all, Collapse all, individual accordion access, and direct return. No reading-progress bar, forced sequence, reviewed badges, mark-reviewed buttons, consent checkboxes, acceptance button, extra pages, new alerts, or approval claims. Both legal documents remain labeled prototype drafts. No rewritten legal text or omitted functionality. Render accurate readable text. Standalone full-bleed UI screenshot with no phone bezel or watermark.
```
## Privacy Policy generation prompt

```text
Use case: ui-mockup
Asset type: one high-fidelity Flutter Android Privacy Policy screen; portrait proportions equivalent to 390 by 844 logical pixels.

Input images:
- Image 1 is the freshly redesigned Terms of Use screen. Match its layout, pale-blue page background, header, numbered accordion panel, margins, typography, separators, buttons, and visual weight precisely.
- Image 2 is the original Privacy Policy page. Use its exact section titles, helper text, and existing interaction.

Primary request:
Create the matching Privacy Policy companion to Image 1. Restrained visual polish for a readable legal document; preserve direct access to all sections with inline accordions, Expand all, Collapse all, and Back to onboarding.

Layout:
Android status bar, then app bar with back arrow and title "Privacy Policy".
Compact pale-blue document header with a small outline shield icon in a pale-blue circle; eyebrow "FLOODSENSE", neutral "Prototype draft" badge, exact metadata "Version prototype-draft-1", and line "Tap a section to read its details."
Slim toolbar "Document sections" and two clearly distinct accessible actions "Expand all" and "Collapse all".

Single continuous white rounded accordion panel with fine light-blue border and thin separators. Each row has a pale-blue small number tile, semibold title, secondary smaller helper text, and down chevron. All rows collapsed. Use exactly these rows:
01 "Who operates this prototype" / "Research operator details"
02 "Contact information" / "Privacy questions and requests"
03 "Account data collected" / "Username, email, and authentication records"
04 "Optional preference data" / "Resident-controlled defaults"
05 "Foreground GPS and temporary pin" / "Location use is user-initiated"
06 "Assessment and scenario selections" / "Inputs used for deterministic classification"
07 "DSS answers" / "Branch answers are not stored by default"
08 "Device, error, and security logging" / "Limited operational records"

White fixed bottom surface with thin divider and safe-area padding; full-width pale-blue outlined button with left arrow "Back to onboarding". Keep visible content above the footer. Natural vertical scrolling handles any further policy sections.

Visual system:
Very pale blue #F1F8FC across the screen, white reading panel, restrained primary #1A94D5 accents, dark navy headings, slate secondary text, barely noticeable gradient. No heavy shadows. The two document screens should look like members of the same Flutter component system.

Constraints:
Do not add step navigation, progress bars, review/approval indicators, mark-reviewed actions, acceptance checkboxes, new legal prose, document completion gates, or settings.
No maps, topographic decoration, illustrations, 3D imagery, giant icons, busy textures, multicolored cards, saturated backgrounds, or draggable footer handles.
Keep prototype status and version truthful and prominent without repeatedly warning inside rows.
Preserve full readable section headings; wrap if necessary. No phone bezel, watermark, or browser chrome.
```
