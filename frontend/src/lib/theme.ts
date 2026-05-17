'use client';

import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  cssVariables: true,
  colorSchemes: { light: true, dark: true },
  palette: {
    mode: 'dark',
    primary: { main: '#7c5cff' },
    secondary: { main: '#22d3ee' },
    background: { default: '#0b0d12', paper: '#13161d' },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: ['var(--font-geist-sans)', 'Inter', 'system-ui', 'sans-serif'].join(','),
    h1: { fontSize: '2rem', fontWeight: 700 },
    h2: { fontSize: '1.5rem', fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
});
