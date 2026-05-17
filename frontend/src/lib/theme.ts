'use client';

import { createTheme } from '@mui/material/styles';

import { colors, radii, typography } from '@/lib/tokens';

const hankenStack = 'var(--font-hanken-grotesk), system-ui, sans-serif';
const interStack = 'var(--font-inter), system-ui, sans-serif';
const monoStack = 'var(--font-jetbrains-mono), ui-monospace, monospace';

const px = (n: number) => `${n}px`;

export const theme = createTheme({
  cssVariables: true,
  colorSchemes: { dark: true },
  palette: {
    mode: 'dark',
    primary: {
      main: colors.primaryContainer,
      light: colors.primary,
      dark: colors.onPrimaryFixedVariant,
      contrastText: colors.onPrimaryContainer,
    },
    secondary: {
      main: colors.secondaryContainer,
      light: colors.secondary,
      dark: colors.onSecondaryContainer,
      contrastText: colors.onSecondaryContainer,
    },
    error: {
      main: colors.errorContainer,
      light: colors.error,
      contrastText: colors.onErrorContainer,
    },
    background: {
      default: colors.background,
      paper: colors.surfaceContainerLow,
    },
    text: {
      primary: colors.onSurface,
      secondary: colors.onSurfaceVariant,
      disabled: colors.outline,
    },
    divider: colors.outlineVariant,
    primaryContainer: { main: colors.primaryContainer, contrastText: colors.onPrimaryContainer },
    secondaryContainer: {
      main: colors.secondaryContainer,
      contrastText: colors.onSecondaryContainer,
    },
    errorContainer: { main: colors.errorContainer, contrastText: colors.onErrorContainer },
    outlineVariant: colors.outlineVariant,
    onSurfaceVariant: colors.onSurfaceVariant,
    surfaceContainerHigh: colors.surfaceContainerHigh,
    surfaceContainerLow: colors.surfaceContainerLow,
  },
  shape: { borderRadius: radii.default },
  typography: {
    fontFamily: interStack,
    h1: {
      fontFamily: hankenStack,
      fontSize: px(typography.displayLg.fontSize),
      fontWeight: typography.displayLg.fontWeight,
      lineHeight: px(typography.displayLg.lineHeight),
      letterSpacing: typography.displayLg.letterSpacing,
    },
    h2: {
      fontFamily: hankenStack,
      fontSize: px(typography.headlineLg.fontSize),
      fontWeight: typography.headlineLg.fontWeight,
      lineHeight: px(typography.headlineLg.lineHeight),
      letterSpacing: typography.headlineLg.letterSpacing,
    },
    h3: {
      fontFamily: hankenStack,
      fontSize: px(typography.titleMd.fontSize),
      fontWeight: typography.titleMd.fontWeight,
      lineHeight: px(typography.titleMd.lineHeight),
    },
    body1: {
      fontFamily: interStack,
      fontSize: px(typography.bodyLg.fontSize),
      fontWeight: typography.bodyLg.fontWeight,
      lineHeight: px(typography.bodyLg.lineHeight),
    },
    body2: {
      fontFamily: interStack,
      fontSize: px(typography.bodySm.fontSize),
      fontWeight: typography.bodySm.fontWeight,
      lineHeight: px(typography.bodySm.lineHeight),
    },
    button: {
      fontFamily: interStack,
      fontSize: px(typography.bodySm.fontSize),
      fontWeight: 600,
      textTransform: 'none',
    },
    displayLg: {
      fontFamily: hankenStack,
      fontSize: px(typography.displayLg.fontSize),
      fontWeight: typography.displayLg.fontWeight,
      lineHeight: px(typography.displayLg.lineHeight),
      letterSpacing: typography.displayLg.letterSpacing,
    },
    labelCaps: {
      fontFamily: monoStack,
      fontSize: px(typography.labelCaps.fontSize),
      fontWeight: typography.labelCaps.fontWeight,
      lineHeight: px(typography.labelCaps.lineHeight),
      letterSpacing: typography.labelCaps.letterSpacing,
      textTransform: 'uppercase',
    },
    codeSm: {
      fontFamily: monoStack,
      fontSize: px(typography.codeSm.fontSize),
      fontWeight: typography.codeSm.fontWeight,
      lineHeight: px(typography.codeSm.lineHeight),
    },
  },
});
