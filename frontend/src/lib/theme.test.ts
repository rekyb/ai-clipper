import { describe, expect, it } from 'vitest';

import { theme } from '@/lib/theme';
import { colors, radii } from '@/lib/tokens';

describe('Vivid Velocity theme wiring', () => {
  it('is dark-mode only (no light scheme)', () => {
    expect(theme.palette.mode).toBe('dark');
    expect(theme.colorSchemes?.light).toBeUndefined();
    expect(theme.colorSchemes?.dark).toBeDefined();
  });

  it('uses Electric Purple primary-container as the action color', () => {
    expect(theme.palette.primary.main).toBe(colors.primaryContainer);
  });

  it('uses Viral Green as the secondary (success) color', () => {
    expect(theme.palette.secondary.main).toBe(colors.secondaryContainer);
  });

  it('exposes the named container palettes for status chips', () => {
    expect(theme.palette.primaryContainer.main).toBe(colors.primaryContainer);
    expect(theme.palette.secondaryContainer.main).toBe(colors.secondaryContainer);
    expect(theme.palette.errorContainer.main).toBe(colors.errorContainer);
  });

  it('sets the surface background to DESIGN.md surface', () => {
    expect(theme.palette.background.default).toBe(colors.background);
  });

  it('uses DESIGN.md outline-variant for dividers', () => {
    expect(theme.palette.divider).toBe(colors.outlineVariant);
  });

  it('uses the 8 px default radius', () => {
    expect(theme.shape.borderRadius).toBe(radii.default);
  });

  it('routes the body font through the Inter CSS variable', () => {
    expect(theme.typography.fontFamily).toMatch(/--font-inter/);
  });

  it('routes h1/h2/h3 through the Hanken Grotesk CSS variable', () => {
    expect(theme.typography.h1.fontFamily).toMatch(/--font-hanken-grotesk/);
    expect(theme.typography.h2.fontFamily).toMatch(/--font-hanken-grotesk/);
    expect(theme.typography.h3.fontFamily).toMatch(/--font-hanken-grotesk/);
  });

  it('uses 48 px for the displayLg variant (display-lg)', () => {
    expect(theme.typography.displayLg.fontSize).toBe('48px');
  });

  it('uses JetBrains Mono for the labelCaps variant', () => {
    expect(theme.typography.labelCaps.fontFamily).toMatch(/--font-jetbrains-mono/);
    expect(theme.typography.labelCaps.textTransform).toBe('uppercase');
  });

  it('uses JetBrains Mono for the codeSm variant', () => {
    expect(theme.typography.codeSm.fontFamily).toMatch(/--font-jetbrains-mono/);
    expect(theme.typography.codeSm.fontSize).toBe('13px');
  });

  it('does not embed raw Geist fonts (Phase 1 placeholder)', () => {
    const serialized = JSON.stringify(theme.typography);
    expect(serialized).not.toMatch(/geist/i);
  });
});
