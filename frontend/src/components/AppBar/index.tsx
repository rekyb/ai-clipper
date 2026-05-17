import { AppBar as MuiAppBar, Box, Toolbar, Typography } from '@mui/material';

import { appBarSurface } from '@/lib/surfaces';

export function AppBar() {
  return (
    <MuiAppBar position="sticky" color="transparent" elevation={0} sx={appBarSurface}>
      <Toolbar>
        <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: 0.5 }}>
          AI Clipper
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
      </Toolbar>
    </MuiAppBar>
  );
}
