import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import yaml from 'js-yaml';
import { describe, expect, it } from 'vitest';

import { colors, motion, radii, spacing, typography } from '@/lib/tokens';

type DesignFrontmatter = {
  colors: Record<string, string>;
  typography: Record<string, { fontFamily: string; fontSize: string; fontWeight: string; lineHeight: string; letterSpacing?: string }>;
  rounded: Record<string, string>;
  spacing: Record<string, string>;
};

function loadDesign(): DesignFrontmatter {
  const path = resolve(__dirname, '../../../DESIGN.md');
  const raw = readFileSync(path, 'utf-8');
  const match = raw.match(/^---\n([\s\S]+?)\n---/);
  if (!match) throw new Error('DESIGN.md frontmatter not found');
  return yaml.load(match[1]) as DesignFrontmatter;
}

function kebabToCamel(key: string): string {
  return key.replace(/-([a-z])/g, (_m, c: string) => c.toUpperCase());
}

const design = loadDesign();

describe('Vivid Velocity color tokens', () => {
  it.each(Object.entries(design.colors))(
    'color "%s" matches DESIGN.md',
    (designKey, designValue) => {
      const tsKey = kebabToCamel(designKey) as keyof typeof colors;
      expect(colors[tsKey]).toBe(designValue);
    },
  );

  it('exposes every color declared in DESIGN.md', () => {
    const designKeys = Object.keys(design.colors).map(kebabToCamel).sort();
    const tokenKeys = Object.keys(colors).sort();
    expect(tokenKeys).toEqual(designKeys);
  });
});

describe('Vivid Velocity radii tokens', () => {
  it('matches rounded values from DESIGN.md', () => {
    const parsed = {
      sm: parseRem(design.rounded.sm),
      default: parseRem(design.rounded.DEFAULT),
      md: parseRem(design.rounded.md),
      lg: parseRem(design.rounded.lg),
      xl: parseRem(design.rounded.xl),
      full: parseInt(design.rounded.full, 10),
    };
    expect(radii).toEqual(parsed);
  });
});

describe('Vivid Velocity spacing tokens', () => {
  it('matches all spacing values from DESIGN.md', () => {
    const parsed = {
      base: parsePx(design.spacing.base),
      xs: parsePx(design.spacing.xs),
      sm: parsePx(design.spacing.sm),
      md: parsePx(design.spacing.md),
      lg: parsePx(design.spacing.lg),
      xl: parsePx(design.spacing.xl),
      gutter: parsePx(design.spacing.gutter),
      marginMobile: parsePx(design.spacing['margin-mobile']),
      marginDesktop: parsePx(design.spacing['margin-desktop']),
    };
    expect(spacing).toEqual(parsed);
  });
});

describe('Vivid Velocity typography tokens', () => {
  it.each([
    ['displayLg', 'display-lg'],
    ['headlineLg', 'headline-lg'],
    ['titleMd', 'title-md'],
    ['bodyLg', 'body-lg'],
    ['bodySm', 'body-sm'],
    ['labelCaps', 'label-caps'],
    ['codeSm', 'code-sm'],
  ])('typography "%s" matches DESIGN.md "%s"', (tsKey, designKey) => {
    const ts = typography[tsKey as keyof typeof typography];
    const designSpec = design.typography[designKey];
    expect(ts.fontFamily).toBe(designSpec.fontFamily);
    expect(ts.fontSize).toBe(parsePx(designSpec.fontSize));
    expect(ts.fontWeight).toBe(parseInt(designSpec.fontWeight, 10));
    expect(ts.lineHeight).toBe(parsePx(designSpec.lineHeight));
  });
});

describe('motion tokens', () => {
  it('exposes the three duration buckets from DESIGN.md §Motion', () => {
    expect(motion.micro).toBe(120);
    expect(motion.standard).toBe(180);
    expect(motion.emphatic).toBe(280);
  });
});

function parseRem(value: string): number {
  if (value.endsWith('rem')) return parseFloat(value) * 16;
  if (value.endsWith('px')) return parseInt(value, 10);
  return parseInt(value, 10);
}

function parsePx(value: string): number {
  return parseInt(value, 10);
}
