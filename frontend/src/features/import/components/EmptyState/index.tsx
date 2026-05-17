import { Box, Stack, Typography } from '@mui/material';
import { FilmIcon } from 'lucide-react';
import type { ReactNode } from 'react';

export function EmptyState({
  icon = <FilmIcon size={48} strokeWidth={1.5} />,
  title,
  body,
  cta,
}: Readonly<{
  icon?: ReactNode;
  title: string;
  body: string;
  cta?: ReactNode;
}>) {
  return (
    <Stack
      alignItems="center"
      spacing={2}
      sx={{ py: 6, mx: 'auto', maxWidth: 320, textAlign: 'center' }}
    >
      <Box sx={{ color: 'text.disabled' }}>{icon}</Box>
      <Typography variant="h3" component="p">
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {body}
      </Typography>
      {cta}
    </Stack>
  );
}
