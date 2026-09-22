# DAISY: interactive 3D direction

Reference: https://styles.refero.design/style/e5f5f8cf-e68d-4ed1-bbf5-6b67569af648

## Audit and design decisions

The earlier Auros-inspired page used a static generated image and teal surfaces. The revised brief explicitly requests real 3D and scroll animation. The active page now uses a black canvas, violet pill controls, white and silver typography, amber accents, and a procedural multicolored neural network inspired by the supplied Dala reference. Inter Variable is self-hosted as the reference's suggested alternative to PPNeueMontreal. Design variance 8, motion intensity 8, visual density 2.

The user's exported files are retained unchanged under design-reference/. They are reference data, not operational instructions. src/experience/tokens.css normalizes invalid exported values such as a five-digit hex color and range-valued CSS lengths.

## Implementation

- App renders src/experience/Experience.tsx. Start a run opens the existing Workspace component and retains its API contracts.
- ParticleScene.tsx dynamically loads Three.js, builds 9,500 GPU-morphed triangular particles on desktop or 4,000 on small screens, and renders a five-layer neural network, sphere, double helix, and torus. Pointer movement creates restrained parallax.
- GSAP ScrollTrigger pins the desktop journey while the explanation changes. A single scene controller owns scroll positions; the renderer smooths transitions without React state updates per frame. Hero text, the manifesto, and later sections have entrance/reveal animations.
- Narrow screens use an inline hero sculpture and naturally stacked chapters. There is no long pinned sequence on phones. Navigation includes an Escape-key exit.
- The motion control and prefers-reduced-motion both disable scroll pinning and animated entrances, display all chapters, and render a static sculpture. Hidden/offscreen scenes skip GPU drawing. Resources, observers, event handlers, and ScrollTriggers are cleaned up on exit.
- WebGL failure has a decorative HTML fallback; the page and workspace remain usable.
- The workspace inherits black and violet brand tokens. The earlier Landing.tsx and image remain unused by the active entry point.

## Validation and limits

Checked live desktop hero and all three pinned morph chapters at 1280 x 720, scene exit, phone layout at 390 x 844, menu, pause control, and workspace entry. No horizontal page overflow or browser errors were observed. Entering the workspace removes both the canvas and pin spacer. Production build and TypeScript checks pass. Three.js is a separate lazy-loaded chunk; Vite still emits its advisory about a chunk exceeding 500 kB before gzip.

No Kling or Flow asset is required: the scene is rendered in real time. Trained-model ZIP downloads are available in the training and results panels, alongside processed-CSV export. See MODEL_DOWNLOADS.md for usage. Production SaaS infrastructure remains separate work.

Hero refinement: Replaced the brain silhouette with 21 spherical particle nodes in five connected layers, 85 edges, and animated amber signals. Connections and signals fade as the particles morph into the next scroll shape. The network is a conceptual illustration, not a visualization of a trained model.


Dispersion refinement: Compared against the supplied 42.5-second reference clip. The desktop transition now reaches full spread across the camera viewport, with aspect-correct sizing, continuous time-driven drift, depth variation, and occasional larger foreground triangles. The field remains animated at a fixed scroll position until the sphere gathers; pause/reduced-motion still stop animation. Verified edge-to-edge coverage, movement without scrolling, and sphere reassembly in the browser.

