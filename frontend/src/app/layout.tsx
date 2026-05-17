import type { Metadata } from 'next';
import { Hanken_Grotesk, Inter, JetBrains_Mono } from 'next/font/google';

import { AppBar } from '@/components/AppBar';
import { Providers } from '@/components/Providers';

import './globals.css';

const hanken = Hanken_Grotesk({
  variable: '--font-hanken-grotesk',
  subsets: ['latin'],
  weight: ['400', '600', '700', '800'],
});
const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
  weight: ['400', '500', '600'],
});
const jetbrains = JetBrains_Mono({
  variable: '--font-jetbrains-mono',
  subsets: ['latin'],
  weight: ['400', '600'],
});

export const metadata: Metadata = {
  title: 'AI Clipper',
  description: 'Local-first AI video clipping for short-form content.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${hanken.variable} ${inter.variable} ${jetbrains.variable}`}
    >
      <body>
        <Providers>
          <AppBar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
