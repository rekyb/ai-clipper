import type { SxProps, Theme } from '@mui/material/styles';

import { colors, radii } from '@/lib/tokens';

const surfaceContainerAlpha = 'rgba(32, 31, 33, 0.8)';
const subtleBorder = 'rgba(255, 255, 255, 0.08)';
const primaryGlow = `0 0 0 1px ${withAlpha(colors.primaryContainer, 0.15)}`;
const primaryHoverBorder = withAlpha(colors.primaryContainer, 0.6);

export const midSurface: SxProps<Theme> = {
  backgroundColor: surfaceContainerAlpha,
  border: '1px solid',
  borderColor: subtleBorder,
  backdropFilter: 'blur(20px)',
  borderRadius: `${radii.default}px`,
};

export const cardSurface: SxProps<Theme> = {
  ...midSurface,
  borderRadius: `${radii.lg}px`,
  transition: 'border-color 180ms cubic-bezier(0.4, 0, 0.2, 1)',
  '&:hover': { borderColor: primaryHoverBorder },
  '@media (prefers-reduced-motion: reduce)': { transition: 'none' },
};

export const highSurface: SxProps<Theme> = {
  ...midSurface,
  backdropFilter: 'blur(20px)',
  boxShadow: primaryGlow,
};

function withAlpha(hex: string, alpha: number): string {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
