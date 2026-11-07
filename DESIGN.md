---
name: Win-back Agent
description: A confident product page for one decision. Warm off-white ground, wine and crimson bands, and one amber action.
colors:
  wine-nav: "#5e1e26"
  wine-950: "#3e0710"
  wine-900: "#5a0b16"
  wine-800: "#6e0e1a"
  wine-700: "#8a1720"
  wine-ink: "#7a0f1c"
  ground: "#f3efee"
  surface: "#faf8f7"
  tint: "#efe6e5"
  line: "#e3d9d8"
  ink: "#221214"
  ink-2: "#6f5d5c"
  amber-400: "#f5b731"
  amber-500: "#efa21b"
  amber-600: "#e28a0b"
  on-amber: "#3b1f05"
  white: "#ffffff"
  on-wine: "#ffffff"
  on-wine-2: "rgb(255 255 255 / 0.78)"
  on-wine-line: "rgb(255 255 255 / 0.16)"
  on-wine-tile: "rgb(255 255 255 / 0.08)"
  success: "#27845b"
  error: "#c0392b"
typography:
  display:
    fontFamily: "Manrope, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(52px, 6.2vw, 104px)"
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Manrope, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(40px, 4.4vw, 72px)"
    fontWeight: 800
    lineHeight: 1.02
    letterSpacing: "-0.04em"
  title:
    fontFamily: "Manrope, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(26px, 1.6vw + 14px, 36px)"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.03em"
  figure:
    fontFamily: "Manrope, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(56px, 5.6vw, 92px)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.04em"
  stat:
    fontFamily: "Manrope, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(44px, 4.4vw, 72px)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.04em"
  lead:
    fontFamily: "Manrope, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(19px, 0.5vw + 15px, 24px)"
    fontWeight: 400
    lineHeight: 1.55
  body:
    fontFamily: "Manrope, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.55
  small:
    fontFamily: "Manrope, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Manrope, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.55
rounded:
  sm: "10px"
  md: "18px"
  lg: "28px"
  pill: "999px"
spacing:
  s-1: "4px"
  s-2: "8px"
  s-3: "12px"
  s-4: "16px"
  s-5: "24px"
  s-6: "32px"
  s-7: "48px"
  s-8: "64px"
  s-9: "96px"
  s-10: "144px"
components:
  button-primary:
    backgroundColor: "{colors.amber-500}"
    textColor: "{colors.on-amber}"
    rounded: "{rounded.pill}"
    padding: "0 26px"
    height: "48px"
  button-primary-lg:
    backgroundColor: "{colors.amber-500}"
    textColor: "{colors.on-amber}"
    rounded: "{rounded.pill}"
    padding: "0 34px"
    height: "60px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "0 26px"
    height: "48px"
  button-secondary-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
  button-link:
    backgroundColor: "transparent"
    textColor: "{colors.wine-ink}"
    padding: "0 8px"
    height: "44px"
  button-link-hover:
    textColor: "{colors.wine-800}"
  input:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "12px 16px"
    height: "52px"
  tag-demo:
    backgroundColor: "{colors.tint}"
    textColor: "{colors.wine-ink}"
    rounded: "{rounded.pill}"
    padding: "0 10px"
    height: "26px"
  global-nav:
    backgroundColor: "{colors.wine-nav}"
    textColor: "{colors.on-wine-2}"
    height: "52px"
  cohort-crimson:
    backgroundColor: "{colors.wine-800}"
    textColor: "{colors.on-wine}"
    rounded: "{rounded.lg}"
    padding: "64px 48px"
  cohort-light:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "64px 48px"
  variant-pill:
    backgroundColor: "{colors.tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    height: "52px"
  result-card:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "48px 48px 32px"
---

# Design System: Win-back Agent

## Overview

**Creative North Star: "The Approval Stage"**

The interface works like a product launch page with one decision on it. A very large, tight Manrope headline states what is at stake. Below it, the evidence comes in bold full-bleed bands: deep crimson fields with white type and amber figures, set between calm warm off-white sections. One bright amber pill carries the only action that matters. Density is low on purpose. Everything is centred, set large, and readable from the back of a room on a projector.

The look and colours follow the user-supplied reference pictures in `frontend/ref_pictures/`, which are binding. Wine is the brand voice. It appears in the nav, in crimson bands and tiles, and in wine-coloured figures on the light ground. Amber is scarce. Depth comes from colour fields and tonal tiles, not from shadows. The one exception is the warm glow under the amber action. There is no dark theme, because the references show none.

Honesty is built into the look. Demo figures are labelled where they appear. Simulated results get their own striped card and are never visually merged with live results.

**Key Characteristics:**
- Warm off-white ground with deep crimson gradient bands and tiles alternating against light surfaces.
- One typeface, Manrope, set at weight 800 with tight negative tracking for headlines and figures.
- Amber reserved for the primary action and for figures and icons on crimson.
- Pills everywhere you can interact: buttons, tags, variant rows, meter track.
- Large soft corners (28px) on cards, centred composition, generous vertical rhythm (96 to 144px bands).
- Requested scroll fade-ins, visible by default. The signature move is the exposure meter filling as its band arrives.

## Colors

A wine-to-crimson brand family on warm, slightly rosy neutrals, with one amber accent kept for action.

### Primary
- **Cellar Wine** (wine-ink): the brand ink on light ground. Hero figure, light-tile headings, result figures, text links, done steps, variant keys, focus ring, input focus border.
- **Crimson Field** (wine-900 to wine-800 to wine-700, a 135deg gradient): the full-bleed guardrails band and the crimson cohort tile. Always carries white text.
- **Nav Wine** (wine-nav): the sticky global nav. It is muted and browner than the crimson field so the nav does not compete with the bands.
- **Deepest Wine** (wine-950): the floor of the wine scale. Reserved for the darkest tonal needs.

### Secondary
- **Harvest Amber** (amber-400, amber-500, amber-600; button fill is a 180deg gradient across all three): the primary action, the exposure meter fill, figures and icons on crimson, variant keys on the crimson tile, the status and current-step dots, the next-step accent icon, and text selection.
- **Amber Ink** (on-amber): text on amber surfaces.

### Neutral
- **Warm Ground** (ground): the page background and the base under the simulated stripes.
- **Paper** (surface): tinted full-width sections, light cohort tiles, the campaign bar (at 94% opacity).
- **Rose Tint** (tint): demo tag and variant pill fills on light surfaces.
- **Hairline** (line): 1px dividers, table and row rules, field borders, step connectors.
- **Near-Black Ink** (ink): headlines, body, secondary button stroke.
- **Muted Ink** (ink-2): leads, captions, labels, notes, upcoming steps.
- **On-Wine White** (on-wine, on-wine-2 at 78%, on-wine-line at 16%, on-wine-tile at 8%): text, secondary text, rules, and tiles on crimson.
- **Functional** (success, error): reserved for states. The error tint is used as the alert background at 10%.

### Named Rules
**The Amber Stays Off Light Text Rule.** Amber is never used for text on the light ground. Amber on #f3efee fails contrast. On light surfaces, emphasis is bold ink or Cellar Wine. A state that needs amber gets an amber dot next to ink text, as with the current step and the status tag.

**The One Bright Action Rule.** Amber fill means "the primary action", and only one action wears it. The sticky bar's small Approve repeats the hero's action rather than adding a second one, and it is hidden on phones. Everything else is an ink-stroked pill or a wine text link.

**The Wine Carries Figures Rule.** Money figures are Cellar Wine on light ground and amber or white on crimson. Figures are never ink-grey.

## Typography

**Display Font:** Manrope (with system-ui, -apple-system, Segoe UI, sans-serif)
**Body Font:** Manrope (same stack)

**Character:** A single geometric-humanist sans that goes from confident and heavy at display sizes to friendly and open at body sizes. Loaded at weights 400 to 800 from Google Fonts.

### Hierarchy
- **Display** (800, clamp 52 to 104px, 0.98, -0.04em): the one hero statement, with the key figure in Cellar Wine.
- **Headline** (800, clamp 40 to 72px, 1.02, -0.04em): section titles, max 16ch, centred. A second line may be set in Muted Ink to work as a two-tone title.
- **Title** (800, clamp 26 to 36px, 1.1, -0.03em): cohort and result headings, the next-step title.
- **Figure / Stat** (800, clamp 56 to 92px and 44 to 72px, line-height 1, -0.04em): money and counts. Units such as "/mo" drop to 0.4em.
- **Lead** (400, clamp 19 to 24px): one or two lines under a headline in Muted Ink, max 40ch.
- **Body** (400, 17px, 1.55): running text, `text-wrap: pretty`.
- **Label** (600, 14px): field labels, table heads, footer headings, system status. Sentence case, no tracking.
- **Buttons** (700, 17px, -0.01em; 15px small, 19px large).

### Named Rules
**The Big and Tight Rule.** Weights 700 and up always get negative tracking (-0.01em to -0.04em). The larger the size, the tighter the tracking.

**The Sentence Case Rule.** No tracked capitals and no kickers or eyebrows above headlines. Status and context that a reference might put in an eyebrow go into the campaign bar as tags.

## Layout

The layout is a centred, single-column narrative of alternating bands. Content is capped at 1040px, and the cohort and results grids at 1240px. Gutters are 40px, dropping to 28px at 1068px and 18px at 734px. Sections and bands use 144px vertical padding (96px on phones), with 64 to 96px between a title block and its content. Spacing follows a 4px-based scale from 4px to 144px.

Navigation is two stacked sticky layers: the 52px wine global nav and the 56px light campaign bar (52px on phones). Anchored sections set `scroll-margin-top` to the combined height. Cohort and result pairs are two-column grids that collapse to one column at 834px. Stats run in four columns, then two columns at 820px. At 820px the nav links become their own horizontally scrollable row under the wordmark. At 734px the campaign bar drops its Approve (the hero carries it), the hero action goes full width, and the step track becomes a balanced grid of four columns.

Text is centred throughout, except inside the meter, variant rows, and data rows, which align left.

## Elevation & Depth

The system is flat. Depth comes from colour fields: the crimson band and crimson tile against the light ground, Paper sections against Warm Ground, and translucent white tiles on crimson. The only shadow is the warm amber glow under the primary action, which grows on hover.

### Shadow Vocabulary
- **Amber Glow** (`box-shadow: 0 14px 30px -12px rgb(226 138 11 / 0.55)`): resting state of the primary pill.
- **Amber Glow Lifted** (`box-shadow: 0 18px 36px -12px rgb(226 138 11 / 0.7)`): primary pill hover, paired with a 1px lift.
- **Focus Halo** (`box-shadow: 0 0 0 4px rgb(122 15 28 / 0.14)`): focused fields.

### Named Rules
**The Colour Is Depth Rule.** Cards and tiles never cast shadows. They separate from the ground by fill alone.

## Shapes

Shapes are soft and generous. Anything interactive or tag-like is a full pill (999px): buttons, tags, variant rows, and the meter track and fill. Cards and tiles use a large 28px radius, fields use 10px, and the focus outline uses 6px. Circles are used for variant keys (32px), result icons (60px), and state dots (8px). Strokes are thin: 1px hairlines, a 1.5px ink stroke on secondary pills, and a 1.5px dashed wine ring on the simulated result icon. Chevrons are drawn from two 1.8px borders rotated 45deg. Icons are inline stroke SVGs on a 24-unit grid.

## Components

### Buttons
Tactile, confident pills.
- **Shape:** full pill (999px), min-height 48px. Small is 40px and large is 60px.
- **Primary:** an amber gradient fill (amber-400 to amber-600) with Amber Ink text at weight 700 and the Amber Glow. It is also the default for any submit button.
- **Hover / Focus:** the primary lifts 1px and its glow deepens. The secondary inverts to an ink fill with Paper text. Press scales to 0.98 with a 1px drop. Focus is a 2px Cellar Wine outline at 3px offset. Hover effects apply only on fine pointers. Under reduced motion, colours still change but nothing moves.
- **Secondary:** transparent with a 1.5px ink stroke and ink text.
- **Link:** Cellar Wine text at weight 600 with a drawn chevron that slides 3px on hover. Used for "Reject proposal".
- **Disabled:** 45% opacity, not-allowed cursor.

### Tags
- **Demo tag:** a Rose Tint pill with Cellar Wine text, 13px/600, 26px high. It labels demo data wherever it is shown.
- **Status tag:** Muted Ink text with a leading 8px amber dot, no fill.

### Cards / Containers
- **Corner Style:** 28px.
- **Background:** Crimson Field or Paper for cohort tiles, which alternate. Results use Paper (live) or a striped Warm Ground (simulated).
- **Shadow Strategy:** none (see Colour Is Depth).
- **Internal Padding:** 64px by 48px for cohorts and 48px for results, reduced to 48px by 24px on phones.

### Inputs / Fields
- **Style:** white fill, 1px Hairline border, 10px radius, min-height 52px, 12px by 16px padding. The label sits above at 14px/600 in Muted Ink.
- **Focus:** the border turns Cellar Wine and a 4px Focus Halo appears.
- **Error:** alerts sit on a 10% error tint with ink text and a 10px radius.

### Navigation
- **Global nav:** sticky Nav Wine bar. The wordmark is 17px/800 with an amber icon. Section links are 14px/500 in 78% white and turn full white on hover, with 44px touch targets. Every link points to a section that exists.
- **Campaign bar:** sticky Paper bar at 94% opacity with a hairline bottom. It holds the campaign name (19px/700), the demo and status tags, and a small primary Approve pinned right.

### Step Track
A horizontal sequence of seven steps at 16px/600, joined by 14px hairline connectors. Done steps are Cellar Wine with a check. Upcoming steps are Muted Ink. The current step is ink at weight 800 with a trailing 8px amber dot.

### Exposure Meter (signature)
An 8px pill track (16% white) on the crimson band. Its amber gradient fill scales from zero to its share over 1100ms with a 250ms delay when the band scrolls into view. The head pairs a white label with an amber 800-weight figure. The meter is the system's signature motion and should stay unique.

### Variant Pills
Rows 52px high, as pills, holding a 32px circular key. On light tiles they are Rose Tint with a wine key carrying white text. On crimson tiles they are 8% white with an amber key carrying Amber Ink text.

### Result Cards (live vs simulated)
Live results sit on Paper with a solid wine icon disc. Simulated results sit on Warm Ground under -45deg wine stripes (5% opacity, 12px bands) with a dashed wine icon ring. The stripes mark simulated data, follow the reference, and are deliberate. Both cards end in hairline-ruled data rows at 24px/800, with winning figures in Cellar Wine. Live and simulated figures are never summed or merged into one card.

### Scroll Reveal
Requested by the user. Content is visible by default. The reveal hook hides only elements below the fold, and only when IntersectionObserver exists and reduced motion is off. Hidden elements fade up 28px over 720ms on the out-curve, staggered 90ms per item. Under reduced motion all reveal and meter transitions are off.

### Footer
A hairline-topped column with the demo-data note (15px, max 60ch, Muted Ink) and a "System status" disclosure using a drawn chevron that flips when open.

## Do's and Don'ts

### Do:
- **Do** keep amber for the primary action and for figures, icons and keys on crimson. On light ground, amber appears only as non-text marks: state dots beside ink text and the single next-step accent icon (amber-600).
- **Do** set headlines and figures in Manrope 800 with tight negative tracking, and put the key figure of a headline in Cellar Wine.
- **Do** alternate crimson and light fields to build rhythm, with 28px corners on tiles and pills for everything interactive.
- **Do** label demo and simulated data where it appears (demo tag, hero note, footer note, striped simulated card). Keep display components prop-driven so real data can replace the demo set.
- **Do** keep content visible by default. Motion is an enhancement that turns off under reduced motion.
- **Do** keep tap targets at least 44px high.

### Don't:
- **Don't** set amber text on the light ground (#f3efee). It fails contrast.
- **Don't** add kickers, eyebrows or tracked capitals above headlines. Put status in campaign-bar tags.
- **Don't** add shadows to cards or tiles. The amber glow belongs to the primary action alone.
- **Don't** add or sum live and simulated figures, or show them in one card.
- **Don't** add a dark theme. The references show none.
- **Don't** give amber fill to any action other than the primary one. Repeating that same action in the campaign bar is fine.
