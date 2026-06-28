---
name: Scholarly Core
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#444653'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#757684'
  outline-variant: '#c4c5d5'
  surface-tint: '#3755c3'
  primary: '#00288e'
  on-primary: '#ffffff'
  primary-container: '#1e40af'
  on-primary-container: '#a8b8ff'
  inverse-primary: '#b8c4ff'
  secondary: '#4e45d5'
  on-secondary: '#ffffff'
  secondary-container: '#6860ef'
  on-secondary-container: '#fffbff'
  tertiary: '#2d3449'
  on-tertiary: '#ffffff'
  tertiary-container: '#434b60'
  on-tertiary-container: '#b4bbd5'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dde1ff'
  primary-fixed-dim: '#b8c4ff'
  on-primary-fixed: '#001453'
  on-primary-fixed-variant: '#173bab'
  secondary-fixed: '#e3dfff'
  secondary-fixed-dim: '#c3c0ff'
  on-secondary-fixed: '#100069'
  on-secondary-fixed-variant: '#372abf'
  tertiary-fixed: '#dae2fd'
  tertiary-fixed-dim: '#bec6e0'
  on-tertiary-fixed: '#131b2e'
  on-tertiary-fixed-variant: '#3f465c'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 0.25rem
  sm: 0.5rem
  md: 1rem
  lg: 1.5rem
  xl: 2.5rem
  gutter: 1.5rem
  margin-mobile: 1rem
  margin-desktop: 2rem
  max-width: 1280px
---

## Brand & Style

This design system is built for high-stakes educational environments, prioritizing clarity, trust, and academic excellence. The brand personality is **Professional, Academic, and Human-Centered**. It aims to reduce cognitive load for students and educators while maintaining a premium, "Gold Standard" SaaS feel.

The design style is **Corporate Modern with Tactile Refinement**. It utilizes a systematic approach to whitespace and hierarchy, ensuring that complex data—such as grades, schedules, and curriculum—remains legible and approachable. The interface avoids unnecessary flourishes, focusing instead on structural integrity and accessibility to evoke an emotional response of reliability and focus.

## Colors

The palette is anchored by **Educational Blue**, a deep, authoritative tone that signals stability. **Secondary Indigo** is used for interactive accents and signaling progression. 

- **Primary & Secondary:** Reserved for core branding, primary actions, and active navigation states.
- **Neutrals:** A slate-tinted gray scale is used to maintain a cool, professional atmosphere, preventing the interface from feeling "flat" or "muddy."
- **Semantic Colors:** Green, Amber, and Red are strictly reserved for feedback (e.g., "Assignment Submitted," "Late Warning," or "Missing Grade").
- **Dark Mode:** In dark mode, surface colors shift to deep slate (`#0F172A`), and primary blues are adjusted for AAA accessibility contrast against dark backgrounds.

## Typography

The design system exclusively uses **Inter** to ensure maximum legibility across all digital touchpoints. 

- **Hierarchy:** Strong contrast between font weights is used to differentiate between administrative labels and student content. 
- **Display & Headlines:** Use tighter letter-spacing and bold weights to create a sense of structure.
- **Body Text:** Standardized at 16px for optimal readability in long-form educational content.
- **Labels:** Uppercase styles are used sparingly for small utility text (e.g., overlines or table headers) to improve scanning.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid** model. On desktop, content is contained within a 1280px max-width 12-column grid to prevent line lengths from becoming unreadable. On mobile, the system transitions to a single-column fluid layout.

- **Spacing Rhythm:** Based on a 4px baseline grid. 16px (`md`) is the standard padding for cards and containers.
- **Vertical Rhythm:** Generous 40px (`xl`) spacing between major sections (e.g., "Upcoming Tasks" vs "Recent Grades") to reduce visual clutter.
- **Mobile-First:** Margins shrink to 16px on mobile devices, with gutters reducing to 12px to maximize screen real estate for content.

## Elevation & Depth

Hierarchy is established through **Tonal Layering** supplemented by **Ambient Shadows**. 

- **Surface Levels:** The background uses a very light gray (`#F8FAFC`). Primary content sits on white cards. 
- **Shadows:** Use highly diffused, low-opacity shadows (Blur: 12px, Y: 4px, Color: `rgba(30, 64, 175, 0.05)`). The subtle blue tint in the shadow maintains brand consistency even in the depth model.
- **Interactive Depth:** Hover states on cards should slightly increase the shadow spread and lift the element by 2px to signal interactivity.
- **Modals:** Use a heavy backdrop blur (8px) to isolate critical user actions like "Submit Exam."

## Shapes

The shape language is **Rounded and Friendly**, balanced by professional constraints. 

- **Standard Radius:** 8px (`0.5rem`) is the default for buttons and input fields, providing a modern, approachable feel.
- **Large Radius:** 16px (`1rem`) is used for primary dashboard cards and containers to soften the overall appearance of data-heavy screens.
- **Pill Shapes:** Used exclusively for status indicators (tags/chips) to distinguish them from actionable buttons.

## Components

### Buttons
Primary buttons use the Primary Blue background with white text. Secondary buttons use a light blue ghost style. All buttons feature an 8px corner radius and a minimum touch target of 44px for mobile accessibility.

### Cards
Cards are the primary organizational unit. They feature a 1px border (`#E2E8F0`) and the ambient blue-tinted shadow. Headers within cards should have a subtle bottom divider.

### Form Inputs
Inputs use a 1px solid border that thickens and changes to Secondary Indigo on focus. Error states use a soft red wash background with a bold red border. Labels are always positioned above the field for clarity.

### Data Tables
Tables are designed for high-density information. They use "Zebra Striping" with a very faint gray (`#F1F5F9`) for even rows. Headers are sticky and use the `label-sm` typography style with a subtle background fill.

### Progress Indicators
Progress bars use a rounded 8px track with the Primary Blue fill. For "Success" states (e.g., Course Completed), the fill transitions to Success Green.

### Chips & Tags
Used for course categories or assignment status. Tags have a soft background (10% opacity of the brand color) and high-contrast text.