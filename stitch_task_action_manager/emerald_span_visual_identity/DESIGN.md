---
name: Emerald Span Visual Identity
colors:
  surface: '#f8f9fa'
  surface-dim: '#d8dadb'
  surface-bright: '#f8f9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f5'
  surface-container: '#eceeef'
  surface-container-high: '#e7e8e9'
  surface-container-highest: '#e1e3e4'
  on-surface: '#191c1d'
  on-surface-variant: '#3c4a3d'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#eff1f2'
  outline: '#6b7b6c'
  outline-variant: '#bacbb9'
  surface-tint: '#006d34'
  primary: '#006d34'
  on-primary: '#ffffff'
  primary-container: '#18e878'
  on-primary-container: '#00632f'
  inverse-primary: '#06e474'
  secondary: '#076b5b'
  on-secondary: '#ffffff'
  secondary-container: '#a0f2dd'
  on-secondary-container: '#157161'
  tertiary: '#306b00'
  on-tertiary: '#ffffff'
  tertiary-container: '#74e421'
  on-tertiary-container: '#2b6100'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#62ff95'
  primary-fixed-dim: '#06e474'
  on-primary-fixed: '#00210b'
  on-primary-fixed-variant: '#005226'
  secondary-fixed: '#a0f2dd'
  secondary-fixed-dim: '#85d6c2'
  on-secondary-fixed: '#00201a'
  on-secondary-fixed-variant: '#005144'
  tertiary-fixed: '#8bfd3d'
  tertiary-fixed-dim: '#70e01a'
  on-tertiary-fixed: '#0a2100'
  on-tertiary-fixed-variant: '#235100'
  background: '#f8f9fa'
  on-background: '#191c1d'
  surface-variant: '#e1e3e4'
typography:
  display-lg:
    fontFamily: Poppins
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 60px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Poppins
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Poppins
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Poppins
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-lg:
    fontFamily: Poppins
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Poppins
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Poppins
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Poppins
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Poppins
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  container-margin: 24px
  gutter: 16px
  stack-sm: 4px
  stack-md: 12px
  stack-lg: 24px
  section-padding: 40px
---

## Brand & Style

The design system for Emerald Span is built on the pillars of **precision, vitality, and connectivity**. It is tailored for professional environments—such as project management, fintech, or enterprise SaaS—where clarity and trust are paramount. 

The aesthetic follows a **Modern Corporate** approach with a high-contrast finish. It prioritizes an "airy" feel through generous whitespace and a clean, light-gray foundation. This is punctuated by vibrant emerald accents that signify growth and forward momentum. The interface feels lightweight yet robust, utilizing sharp typography and subtle tonal layering to organize complex information without visual clutter.

## Colors

The palette is anchored by **Emerald Green**, used strategically to draw attention to primary actions and success states. 

- **Primary (#18E878):** A vibrant, high-energy green for primary buttons, active icons, and growth trends.
- **Secondary (#086B5B):** A deep, forest-toned emerald used for branding, headers, and grounded UI elements to ensure professional weight.
- **Neutral Backgrounds:** A clean `#FFFFFF` for primary surfaces, paired with a very soft `#F2F5F3` for secondary containers and sidebars to create depth without harsh lines.
- **Typography:** A deep charcoal/black (`#1A1D1E`) provides maximum legibility against the light background, ensuring an accessible experience.

## Typography

This design system uses **Poppins** across all levels to maintain a geometric, clean, and friendly professional tone. 

The hierarchy is strictly enforced through weight. Bold and SemiBold weights are reserved for headers and titles to provide a strong visual anchor. Regular weights are used for body text to ensure maximum readability in data-heavy views. Labels use a slightly heavier weight and occasional uppercase styling to distinguish them from standard body copy.

## Layout & Spacing

The design system utilizes a **12-column fluid grid** for desktop, transitioning to a **4-column grid** for mobile. 

- **The 8px Rule:** All spacing and sizing must be a multiple of 8px to maintain mathematical harmony.
- **Airy Margins:** Page containers utilize 24px side margins on mobile and up to 80px on large desktops to push content toward the center and maintain focus.
- **Information Density:** While the overall aesthetic is "airy," data tables and lists should maintain a compact 12px vertical padding to ensure utility isn't sacrificed for style.

## Elevation & Depth

Hierarchy is established primarily through **Tonal Layers** and extremely soft **Ambient Shadows**.

- **Surfaces:** The base page is `#F2F5F3`. Elements like cards and the main content area are raised using a pure white (`#FFFFFF`) surface.
- **Shadows:** Use low-opacity green-tinted shadows for active states. A standard elevation shadow should be `0px 4px 20px rgba(8, 107, 91, 0.04)`.
- **Borders:** Instead of heavy shadows, use 1px solid borders in `#E0E6E2` for card outlines to keep the interface feeling crisp and professional.

## Shapes

The design system uses a **Rounded** shape language to balance the "sharp" corporate feel with an approachable, modern edge.

- **Standard Radius:** 8px (0.5rem) for buttons, input fields, and standard cards.
- **Large Radius:** 16px (1rem) for main dashboard containers or highlight banners.
- **Full Radius:** Used exclusively for tags, badges, and avatars to create a distinct visual contrast against rectangular UI blocks.

## Components

### Buttons
- **Primary:** Solid `#18E878` fill with `#086B5B` text or white text. High-contrast, no shadow.
- **Secondary:** Outline style with `#086B5B` border and text.
- **Tertiary:** Ghost style (text only) with green hover states.

### Form Elements
- **Inputs:** White background, 1px `#E0E6E2` border. On focus, the border shifts to `#18E878` with a 2px outer glow.
- **Selection:** Checkboxes and Radios use the Primary green for the "selected" state.

### Cards & Navigation
- **Cards:** White background with a subtle border. Padding should be a consistent 24px.
- **Sidebar:** Light gray background (`#F2F5F3`) with active states highlighted by a soft green pill background and dark forest green text.

### Feedback Indicators
- **Badges:** Use a "Light fill" pattern—e.g., a "Success" badge has a 10% opacity green background with 100% opacity green text. This keeps the UI light and non-aggressive.