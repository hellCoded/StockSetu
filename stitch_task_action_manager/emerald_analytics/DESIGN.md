---
name: Emerald Analytics
colors:
  surface: '#001713'
  surface-dim: '#001713'
  surface-bright: '#0d4039'
  surface-container-lowest: '#00110e'
  surface-container-low: '#00201c'
  surface-container: '#002520'
  surface-container-high: '#00302a'
  surface-container-highest: '#063c35'
  on-surface: '#bbece2'
  on-surface-variant: '#bacbb9'
  inverse-surface: '#bbece2'
  inverse-on-surface: '#003731'
  outline: '#859585'
  outline-variant: '#3c4a3d'
  surface-tint: '#06e474'
  primary: '#87ffa6'
  on-primary: '#003918'
  primary-container: '#18e878'
  on-primary-container: '#00632f'
  inverse-primary: '#006d34'
  secondary: '#81f131'
  on-secondary: '#163800'
  secondary-container: '#65d401'
  on-secondary-container: '#255600'
  tertiary: '#b7f2e7'
  on-tertiary: '#003731'
  tertiary-container: '#9bd6cb'
  on-tertiary-container: '#235e56'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#62ff95'
  primary-fixed-dim: '#06e474'
  on-primary-fixed: '#00210b'
  on-primary-fixed-variant: '#005226'
  secondary-fixed: '#8bfd3d'
  secondary-fixed-dim: '#70e01a'
  on-secondary-fixed: '#0a2100'
  on-secondary-fixed-variant: '#235100'
  tertiary-fixed: '#b3eee3'
  tertiary-fixed-dim: '#97d2c7'
  on-tertiary-fixed: '#00201c'
  on-tertiary-fixed-variant: '#0f5047'
  background: '#001713'
  on-background: '#bbece2'
  surface-variant: '#063c35'
typography:
  headline-lg:
    fontFamily: Be Vietnam Pro
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Be Vietnam Pro
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Be Vietnam Pro
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Be Vietnam Pro
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Be Vietnam Pro
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Be Vietnam Pro
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Be Vietnam Pro
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Be Vietnam Pro
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Be Vietnam Pro
    fontSize: 10px
    fontWeight: '500'
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
  xs: 4px
  sm: 12px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 32px
---

## Brand & Style

This design system is built for a professional project management and analytics platform that demands high performance, clarity, and a modern edge. The brand personality is authoritative yet energizing—combining deep, stable tones with vibrant, high-contrast highlights that signal growth and momentum.

The design style is **Corporate Modern with Glassmorphic accents**. It utilizes a sophisticated dark mode foundation to reduce eye strain during long analytical sessions, while employing subtle translucency and "glow" effects to direct user focus toward critical data points and primary actions. The visual language conveys precision, technical excellence, and a forward-thinking approach to data visualization.

## Colors

The palette is rooted in a "Deep Forest" spectrum, providing a high-performance dark environment that makes analytical data pop.

- **Primary (#18E878):** A vibrant emerald green used for primary actions, success states, and key data trend lines.
- **Secondary (#8DFF3F):** A lime-tinted accent used sparingly for highlights, secondary data points, and interactive hover states to create a sense of luminosity.
- **Tertiary & Neutrals (#0B4D45, #063C35):** These define the structural layers of the UI. The darkest shade is reserved for the base background, while the lighter forest green is used for cards, sidebars, and elevated surfaces.
- **Text (#F5F7F4):** An off-white, high-contrast neutral ensures maximum legibility against the dark background without the harshness of pure white.

## Typography

This design system utilizes **Be Vietnam Pro** (as a high-quality alternative to Poppins that offers better technical legibility) across all levels. The typography is characterized by its geometric clarity and generous x-height, making it ideal for dense data displays.

Headlines should use **Bold (700)** or **SemiBold (600)** weights to establish clear hierarchy. Body text remains at **Regular (400)** for optimal flow. Labels and metadata use a slightly heavier weight and increased letter spacing to remain distinct at smaller scales. For mobile, headline sizes are reduced to ensure headlines do not wrap excessively, maintaining the "dashboard" feel even on small screens.

## Layout & Spacing

The layout follows a **Fluid Grid** model to accommodate the vast amount of data inherent in project management. 

- **Desktop:** 12-column grid with a 24px gutter. Content is housed in modular cards that span variable column widths (typically 3, 4, 6, or 12).
- **Tablet:** 8-column grid with 20px gutters. Cards reflow to stack vertically or occupy full width.
- **Mobile:** 4-column grid with 16px gutters. Sidebars transition into a bottom-anchored navigation bar or a hamburger drawer.

Spacing follows a strict 8px linear scale to ensure mathematical harmony across the UI. Padding within cards should be consistent (24px) to allow the data to breathe against the dark background.

## Elevation & Depth

Hierarchy in this design system is achieved through **Tonal Layering** and **Subtle Glows** rather than traditional heavy shadows.

1.  **Base Layer:** The darkest emerald (#031F1B) acts as the canvas.
2.  **Surface Layer:** Cards and containers use #0B4D45. They feature a very fine, 1px low-opacity border (#FFFFFF10) to define edges against the dark background.
3.  **Active Elevation:** When an element is focused or active (like a selected navigation item), it receives a soft back-glow using a feathered version of the Primary color (#18E878) at 10-15% opacity.
4.  **Glassmorphism:** Overlays (modals, dropdowns) use a background blur (20px) with a semi-transparent fill of the Surface color to maintain context while focusing the user's attention.

## Shapes

The shape language is **Rounded**, striking a balance between professional structure and modern friendliness. 

- **Standard Elements:** Buttons, input fields, and small UI components use a 0.5rem (8px) corner radius.
- **Containers:** Large cards and dashboard modules use a 1rem (16px) corner radius to create a soft, grouped appearance.
- **Pill Elements:** Status chips and tags use a fully rounded (pill) radius to distinguish them from interactive buttons.

## Components

- **Buttons:** Primary buttons are solid #18E878 with dark text. Secondary buttons use an outline style with #18E878 borders. Hover states should introduce a slight outer glow.
- **Input Fields:** Use a dark fill (#063C35) with a 1px border. On focus, the border transitions to the Primary Emerald color with a subtle inner shadow.
- **Chips & Tags:** Small, pill-shaped indicators. Use low-opacity versions of the Primary/Secondary colors for background fills to keep them subordinate to main actions.
- **Cards:** The workhorse of the dashboard. They must include a consistent 24px internal padding and should never use heavy drop shadows; use the tonal layering and fine borders defined in the Elevation section.
- **Data Visualizations:** Charts should exclusively use the Primary (#18E878) and Secondary (#8DFF3F) colors for data lines/bars. Use gradients that fade into the background color to create the "Emerald Span" signature look.
- **Checkboxes/Radios:** When active, these should be solid Primary color with a white checkmark/dot to ensure they are the most visible small-scale element on the screen.