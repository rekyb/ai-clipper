import { AppBar as MuiAppBar, Box, Toolbar, Typography } from '@mui/material';

export function AppBar() {
  return (
    <MuiAppBar position="sticky" color="transparent" elevation={0}>
      <Toolbar sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: 0.5 }}>
          AI Clipper
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
      </Toolbar>
    </MuiAppBar>
  );
}
