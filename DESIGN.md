---
name: Vivid Velocity
colors:
  surface: '#131315'
  surface-dim: '#131315'
  surface-bright: '#39393b'
  surface-container-lowest: '#0e0e10'
  surface-container-low: '#1b1b1d'
  surface-container: '#201f21'
  surface-container-high: '#2a2a2c'
  surface-container-highest: '#353437'
  on-surface: '#e5e1e4'
  on-surface-variant: '#d0c2d5'
  inverse-surface: '#e5e1e4'
  inverse-on-surface: '#303032'
  outline: '#998d9e'
  outline-variant: '#4d4353'
  surface-tint: '#e0b6ff'
  primary: '#e0b6ff'
  on-primary: '#4c007d'
  primary-container: '#9d4edd'
  on-primary-container: '#fffdff'
  inverse-primary: '#8433c4'
  secondary: '#41ee8d'
  on-secondary: '#00391b'
  secondary-container: '#00d174'
  on-secondary-container: '#00532b'
  tertiary: '#edc156'
  on-tertiary: '#3f2e00'
  tertiary-container: '#947000'
  on-tertiary-container: '#fffdff'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#f2daff'
  primary-fixed-dim: '#e0b6ff'
  on-primary-fixed: '#2e004e'
  on-primary-fixed-variant: '#6a0baa'
  secondary-fixed: '#5dff9e'
  secondary-fixed-dim: '#2fe283'
  on-secondary-fixed: '#00210e'
  on-secondary-fixed-variant: '#00522a'
  tertiary-fixed: '#ffdf9a'
  tertiary-fixed-dim: '#edc156'
  on-tertiary-fixed: '#251a00'
  on-tertiary-fixed-variant: '#5a4300'
  background: '#131315'
  on-background: '#e5e1e4'
  surface-variant: '#353437'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
  title-md:
    fontFamily: Hanken Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 48px
  xl: 80px
  gutter: 20px
  margin-mobile: 16px
  margin-desktop: 32px
---

## Brand & Style
The design system is engineered for the high-velocity world of content creation, specifically optimized for long-to-short form video transformation. The aesthetic follows a **Modern Glassmorphism** approach, utilizing deep layered surfaces and vibrant neon accents to create a high-energy "Pro-Tool" atmosphere.

The interface prioritizes focus by keeping the workspace dark and immersive, allowing video content to remain the focal point. By mixing a professional utility-first layout with expressive, energetic accents, the system evokes a sense of both technical precision and creative inspiration. It is designed to feel like a high-performance engine for the modern creator.

## Colors
This design system utilizes a high-contrast dark theme to minimize eye strain during long editing sessions and to make video colors pop.

- **Primary (Electric Purple):** Used for primary actions, active states, and progress indicators. It represents the "magic" of AI processing.
- **Secondary (Viral Green):** Reserved exclusively for virality scores, growth metrics, and "Success" states (e.g., Export Complete).
- **Neutral/Background:** A deep charcoal-near-black (#0A0A0B) serves as the base.
- **Surface:** Layered deep grays with slight transparency are used to create depth.
- **Glows:** Low-opacity radial gradients using the Primary and Secondary colors are used sparingly behind high-priority badges or active timeline markers.

## Typography
The typography strategy balances bold, high-energy headlines with functional, technical labels. 

**Hanken Grotesk** provides a sharp, modern geometric feel for large titles and navigation, evoking a tech-forward brand. **Inter** is used for the transcript and settings to ensure maximum legibility and reduced cognitive load during dense information processing. **JetBrains Mono** is introduced for technical data, timecodes, and virality metrics to reinforce the "pro-suite" precision of the tool.

## Layout & Spacing
The layout follows a **Fluid Editor Model**. The sidebar and utility panels are fixed in width (280px-320px), while the central workspace (video player and timeline) expands to fill the viewport.

- **Grid:** Use a 12-column grid for dashboard views, but switch to a flexible pane-based layout for the editing workspace.
- **Rhythm:** An 8px base unit governs all padding and margins.
- **Negative Space:** Generous whitespace (48px+) is maintained around the video player to eliminate visual clutter, while settings panels use tighter spacing (12px-16px) for a high-density, professional feel.

## Elevation & Depth
Depth is created through **Tonal Layering and Glassmorphism** rather than traditional heavy shadows.

- **Base Level:** Deep charcoal (#0A0A0B).
- **Mid Level (Panels):** Semi-transparent surface (#1E1E22 at 80% opacity) with a 1px solid border (White at 8% opacity).
- **High Level (Modals/Popovers):** Surface with a backdrop blur (20px) and a subtle outer glow using the Primary color at 10% opacity.
- **Active Indicators:** Items that are "Active" or "Selected" receive a Primary-tinted inner glow and a more vibrant border.

## Shapes
The shape language is "Softly Technical." 

Standard components use a 0.5rem (8px) radius to feel modern and accessible. Interactive elements like buttons and input fields use this consistent rounding. Secondary elements like video thumbnails and virality badges use 1rem (16px) to stand out as distinct objects within the grid. This variation helps differentiate between "UI controls" and "Content objects."

## Components
- **Buttons:** Primary buttons are solid Electric Purple with white text. Secondary buttons are ghost-style with a subtle white border. "Viral" action buttons use a subtle green glow on hover.
- **Virality Badges:** High-contrast pills with a dark background and Electric Green text/icons. Include a tiny "sparkle" icon for scores above 90.
- **Cards:** Content cards use the glassmorphic style. The video preview should have a 1px border that illuminates in Purple when hovered.
- **Input Fields:** Darker than the surface color, with a subtle 1px bottom border that expands into a full border highlight on focus.
- **Timeline:** The playhead is a high-visibility Electric Purple line. Markers for "AI Clips" are indicated with vibrant Purple notches.
- **Chips:** Small, low-contrast tags for video categories, becoming vibrant only when selected to avoid distracting from the main video content.