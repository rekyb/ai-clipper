import { describe, expect, it } from 'vitest';

import { cardSurface, highSurface, midSurface } from './surfaces';

describe('Vivid Velocity surface recipes', () => {
  it('midSurface applies the DESIGN.md mid-level glass tint + border', () => {
    const s = midSurface as Record<string, unknown>;
    expect(s.backgroundColor).toMatch(/^rgba\(32, 31, 33, 0\.8\)$/);
    expect(s.border).toBe('1px solid');
    expect(s.borderColor).toBe('rgba(255, 255, 255, 0.08)');
    expect(s.backdropFilter).toBe('blur(20px)');
  });

  it('cardSurface uses the larger content-object radius (16 px)', () => {
    expect((cardSurface as Record<string, unknown>).borderRadius).toBe('16px');
  });

  it('cardSurface defines the hover-illuminate transition', () => {
    const s = cardSurface as Record<string, unknown>;
    expect(s.transition).toMatch(/border-color 180ms/);
  });

  it('cardSurface honors prefers-reduced-motion', () => {
    const s = cardSurface as Record<string, Record<string, unknown>>;
    const reduce = s['@media (prefers-reduced-motion: reduce)'];
    expect(reduce.transition).toBe('none');
  });

  it('highSurface adds the subtle Primary glow per DESIGN.md High Level', () => {
    const s = highSurface as Record<string, unknown>;
    expect(s.boxShadow).toMatch(/rgba\(157, 78, 221, 0\.15\)/);
  });
});
