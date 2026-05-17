import { Box, Container, Stack, Typography } from '@mui/material';

export default function Home() {
  return (
    <Container maxWidth="lg" sx={{ py: 6 }}>
      <Stack spacing={2}>
        <Typography variant="h1">AI Clipper</Typography>
        <Typography variant="body1" color="text.secondary">
          Local-first video clipping. Phase 1 scaffold ready.
        </Typography>
        <Box
          sx={{
            mt: 2,
            p: 3,
            border: 1,
            borderColor: 'divider',
            borderRadius: 2,
            bgcolor: 'background.paper',
          }}
        >
          <Typography variant="h2" gutterBottom>
            Next up
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Phase 2 brings video import, transcription, and a real-time progress UI.
          </Typography>
        </Box>
      </Stack>
    </Container>
  );
}
