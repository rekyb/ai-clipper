import { Container, Stack } from '@mui/material';

import { ImportPanel } from '@/features/import/components/ImportPanel';
import { VideoLibrary } from '@/features/import/components/VideoLibrary';

export default function Home() {
  return (
    <Container maxWidth="lg" sx={{ py: 6 }}>
      <Stack spacing={6}>
        <ImportPanel />
        <VideoLibrary />
      </Stack>
    </Container>
  );
}
