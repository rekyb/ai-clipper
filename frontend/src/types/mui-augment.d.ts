import '@mui/material/styles';

declare module '@mui/material/styles' {
  interface Palette {
    primaryContainer: Palette['primary'];
    secondaryContainer: Palette['primary'];
    errorContainer: Palette['primary'];
    outlineVariant: string;
    onSurfaceVariant: string;
    surfaceContainerHigh: string;
    surfaceContainerLow: string;
  }
  interface PaletteOptions {
    primaryContainer?: PaletteOptions['primary'];
    secondaryContainer?: PaletteOptions['primary'];
    errorContainer?: PaletteOptions['primary'];
    outlineVariant?: string;
    onSurfaceVariant?: string;
    surfaceContainerHigh?: string;
    surfaceContainerLow?: string;
  }

  interface TypographyVariants {
    labelCaps: React.CSSProperties;
    codeSm: React.CSSProperties;
    displayLg: React.CSSProperties;
  }
  interface TypographyVariantsOptions {
    labelCaps?: React.CSSProperties;
    codeSm?: React.CSSProperties;
    displayLg?: React.CSSProperties;
  }
}

declare module '@mui/material/Typography' {
  interface TypographyPropsVariantOverrides {
    labelCaps: true;
    codeSm: true;
    displayLg: true;
  }
}
