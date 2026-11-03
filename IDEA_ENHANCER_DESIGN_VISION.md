# Idea Enhancer — Design Vision & Deferred UI Enhancements

**Status:** Approved direction for future implementation  
**Scope:** Frontend experience only. Do not implement until the current frontend is stable and backend integration has been tested.

## Purpose

Make Idea Enhancer feel distinctive, responsive, and thoughtfully crafted—not simply like a conventional web form with a spinner.

Two connected interactions are planned:

1. A progressive glass-and-pencil search experience.
2. An ambient sun-to-moon light/dark theme transition.

The visuals should feel integrated with the existing page, not layered on as unrelated decorations.

---

## 1. Search Progress: Pencil Drawing Through Glass

### Intended experience

When the user submits an idea:

1. Keep the existing page visible rather than replacing it with a conventional full-screen loading page.
2. At the beginning of the search, cover the interface with an **opaque or near-opaque layer** so the underlying page is initially hidden or strongly obscured. This is intentional: the effect starts opaque, not transparent.
3. Show a clean, two-dimensional pencil drawing a progress line. The pencil tip should track the end of the line so it appears to be drawing it.
4. As search progress advances, the pencil draws farther along the line and the overlay gradually becomes more transparent, progressively revealing the interface beneath it. The transition runs from **opaque to transparent**—the reverse of making the overlay more opaque as progress increases. Any blur should be restrained and coordinated with this reveal.
5. Use a short status message to indicate what the system is doing in language suitable for the user. Do not expose internal algorithm, database, or model names on the public page.
6. When the search completes successfully, finish the drawing, make the overlay fully transparent or remove it, and reveal the results with a restrained transition.
7. When the search fails, stop the progress animation cleanly, remove or fade the overlay, and show a clear, accessible error state. Never leave the page stuck under glass.

### Progress must be truthful

The existing `POST /search` request does not, by itself, provide intermediate search progress. A browser knowing that a request has started or that bytes are transferring is not the same as knowing how far backend computation has progressed.

Before implementing true progress, coordinate with the API and core-search owners to identify real search milestones and whether the backend can report them.

Preferred direction:

- Have the backend emit meaningful stage updates if this is practical for the agreed architecture.
- Consider Server-Sent Events (SSE) if continuous updates are needed and acceptable to the team.
- Avoid introducing background-job infrastructure solely for this animation unless search duration or other product requirements justify it.
- Preserve the current `POST /search` contract unless a coordinated, documented API change is approved.

If the backend can report only milestones rather than an exact percentage, use actual milestones as anchors. Any smooth interpolation between them is a visual estimate, not a measured percentage of computation. Do not mislead users into thinking an arbitrary animated number is exact.

If searches usually complete very quickly, prefer a subtle short animation over artificial waiting.

### Visual direction

- Two-dimensional pencil illustration; no need for a 3D model.
- A clear, elegant line with a refined indigo accent that matches the existing visual identity.
- An initially opaque or near-opaque glass-like overlay that becomes increasingly transparent as progress advances.
- The underlying interface is progressively revealed; do not animate from transparent to opaque.
- Smooth, connected motion: the pencil, filled line, overlay transparency, and status change should feel like one system.
- Avoid excessive particles, neon effects, distracting movement, or an animation that delays access to finished results.

---

## 2. Theme Easter Egg: Sun and Moon Control the Ambient Light

### Core concept

A recognisable illustrated sun sits in a corner of the interface in light mode. Clicking it transitions the page into dark mode. The sun sets or falls away smoothly, and a crescent moon emerges in its place. Clicking the moon reverses the transition and returns the interface to light mode.

The interaction should feel like the celestial object is controlling the environment—not like an ordinary theme icon whose only effect is swapping colours.

### Sun — light mode

- A polished, two-dimensional sun illustration with a clear circular body and recognisable rays.
- No face, eyes, mouth, cartoon character, or emoji styling.
- No enclosing button tile or contrasting card background. The illustration should sit directly on the page background and visually blend into it.
- Warm golden-yellow light, with a soft radial halo.
- A recognisable presence: not tiny and easy to miss, but not so large that it competes with the product or occupies significant interface space.
- The rays and illumination should softly brighten and warm the surrounding background. Nearby surfaces may receive restrained warm highlights; shadows should remain subtle.

### Moon — dark mode

- A refined two-dimensional crescent, visually comparable in scale and quality to the sun.
- No face or cartoon styling.
- No enclosing tile or panel behind the moon.
- Muted silver/lavender tones and a very subtle glow; avoid glaring white light.
- The moon's cool light should blend into a deep navy background. Cards, borders, shadows, and typography should transition into the corresponding dark theme so the moonlight feels connected to the whole interface.
- Keep stars or decorative details minimal; the moon and the ambient light are the focus.

### Believable lighting transition

On switching from light to dark:

1. The sun moves downward or otherwise recedes smoothly.
2. Its warm glow gradually fades across the background.
3. The overall page transitions from the current warm ivory/light palette to a carefully designed dark palette.
4. A crescent moon emerges into view.
5. A faint cool silver-lavender halo spreads around the moon and subtly influences nearby background surfaces.

Switching back should reverse the sequence: the moon recedes, moonlight fades, daylight warms the page, and the sun returns.

Use layered CSS radial gradients and theme variables where practical. The lighting should affect the overall environment—background, surfaces, borders, and shadows—not just the illustrated object. Avoid giant visible beams, harsh neon rings, or overdone glow effects.

### Easter egg and accessibility

- Do not add visible explanatory copy announcing the theme-switching trick. The animation should be a small, delightful discovery.
- The control must still have an accessible name, keyboard support, and a visible focus treatment.
- Respect `prefers-reduced-motion`; provide a simpler, shorter transition for users who request reduced motion.
- Persist the user's theme choice if appropriate, and define sensible behavior for first visit and system preference.
- Ensure contrast and usability remain strong in both themes. The visual effect must not impair readability or make controls hard to locate.

---

## 3. Shared Motion and Visual Principles

Both interactions should feel like parts of one design language:

- Smooth, restrained, intentional movement.
- Light and translucency should feel ambient and connected to the page.
- Clear hierarchy: animations support the content rather than competing with it.
- Maintain the existing light editorial design as the baseline; dark mode should feel equally designed, not like a quick inversion.
- No fake performance metrics, invented progress, fabricated search results, or claims unsupported by the backend.
- Keep interactions responsive and avoid unnecessary animation time.
- Retain semantic HTML, safe DOM construction, keyboard operation, focus visibility, and reduced-motion support.

---

## 4. Implementation Sequence and Dependencies

Do not start either enhancement until the existing frontend corrections are reviewed and the current search journey is stable.

### Stage A — Stabilise the existing application

- Test the current mock scenarios and error states in a real browser.
- Verify stale results, mode changes, request cancellation, response validation, timeout handling, and `top_k` behavior.
- Integrate and test the real FastAPI search path.
- Keep mock data visibly distinct from actual backend results.

### Stage B — Establish backend progress semantics

- Ask the API and core-search owners which stages exist and how long they typically take.
- Decide whether real stage reporting is warranted.
- If needed, agree on a backward-compatible or formally approved progress interface before implementation.
- Define behavior for fast completion, failures, cancellations, and missing progress updates.

### Stage C — Build the pencil-and-glass search experience

- Implement the overlay and pencil as a focused feature.
- Connect milestones to backend updates where available.
- Keep any estimated interpolation distinct from measured progress.
- Test success, no-match, validation error, server error, timeout, cancellation, and reduced-motion states.
- Confirm the overlay starts opaque or near-opaque and becomes progressively transparent as progress advances, with the pencil drawing in sync.

### Stage D — Build the sun/moon ambient theme transition

- Define light and dark theme tokens for backgrounds, text, surfaces, borders, and shadows.
- Create or implement the sun and crescent illustrations as background-free two-dimensional assets or inline vector artwork.
- Animate celestial movement and the warm-to-cool environmental lighting transition together.
- Add persistence, keyboard support, accessible naming, and reduced-motion handling.
- Test the transition across desktop and mobile layouts and verify contrast in both themes.

### Stage E — Final quality pass

- Test in a real browser at narrow phone, tablet, and desktop widths.
- Check for layout shifts, content obscured by overlays, stuck transitions, and console errors.
- Confirm the animations do not add meaningful delays to search results.
- Confirm no internal algorithm/model names leak into the public UI.

---

## 5. Non-Goals and Guardrails

- Do not rebuild the application in a new framework for these effects.
- Do not change backend interfaces or shared contract documents without the relevant owner's agreement.
- Do not add a complex graphics engine just to create the sun, moon, pencil, or glow.
- Do not claim exact search progress without backend evidence.
- Do not begin these enhancements at the cost of breaking the existing working search, accessibility, or responsive layout.

---

## Final Design Principle

**The sun and moon should feel like the sources of the page's light and darkness. The pencil should feel as though it is physically drawing the search progress.**

Both effects should be believable, elegant, restrained, and integrated with the rest of Idea Enhancer—not merely decorative pictures or generic loading animations.