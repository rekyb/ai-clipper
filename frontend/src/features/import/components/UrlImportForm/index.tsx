'use client';

import { Box, Button, Stack, TextField, Typography } from '@mui/material';
import { LinkIcon } from 'lucide-react';
import { useState } from 'react';

import { useImportUrl } from '@/features/import/hooks/useImportUrl';
import { midSurface } from '@/lib/surfaces';

const YOUTUBE_HOST_RE = /^(https?:\/\/)?(www\.|m\.)?(youtube\.com|youtu\.be)\b/i;

export function UrlImportForm() {
  const { importUrl, isImporting, error, reset } = useImportUrl();
  const [url, setUrl] = useState('');
  const [hint, setHint] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setHint(null);
    if (!YOUTUBE_HOST_RE.test(url.trim())) {
      setHint('Only YouTube URLs are supported (youtube.com, youtu.be).');
      return;
    }
    reset();
    const result = await importUrl(url.trim());
    if (result) setUrl('');
  };

  return (
    <Box
      component="form"
      onSubmit={onSubmit}
      sx={{
        ...midSurface,
        minHeight: 200,
        height: '100%',
        p: 3,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
      }}
    >
      <Stack spacing={2}>
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ color: 'text.secondary' }}>
          <LinkIcon size={20} strokeWidth={1.5} />
          <Typography variant="body2">Paste a YouTube link</Typography>
        </Stack>
        <TextField
          placeholder="https://youtu.be/..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={isImporting}
          fullWidth
          inputProps={{ 'aria-label': 'YouTube URL' }}
        />
        <Button
          type="submit"
          variant="contained"
          color="primary"
          size="large"
          disabled={isImporting || url.trim().length === 0}
          fullWidth
        >
          {isImporting ? 'Importing…' : 'Import from URL'}
        </Button>
        <Typography
          component="span"
          sx={{
            fontFamily: 'var(--font-jetbrains-mono), ui-monospace, monospace',
            fontSize: 12,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: 'text.disabled',
            textAlign: 'center',
          }}
        >
          youtube.com · youtu.be
        </Typography>
        {hint && (
          <Typography variant="body2" color="warning.main">
            {hint}
          </Typography>
        )}
        {error && (
          <Typography variant="body2" color="error.main">
            {error.message}
          </Typography>
        )}
      </Stack>
    </Box>
  );
}
