'use client';

import { Box, Stack, Typography } from '@mui/material';

import { UploadDropzone } from '@/features/import/components/UploadDropzone';
import { UrlImportForm } from '@/features/import/components/UrlImportForm';

export function ImportPanel() {
  return (
    <Box>
      <Typography variant="h2" sx={{ mb: 3 }}>
        Import a video
      </Typography>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={3}
        alignItems="stretch"
      >
        <Box sx={{ flex: { xs: 1, md: 3 } }}>
          <UploadDropzone />
        </Box>
        <Box sx={{ flex: { xs: 1, md: 2 } }}>
          <UrlImportForm />
        </Box>
      </Stack>
    </Box>
  );
}
