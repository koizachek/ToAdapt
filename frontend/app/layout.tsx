import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ToAdapt — Studie',
  description: 'Business Case Study mit Business Model Canvas',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Serif+Display:ital@0;1&display=swap" rel="stylesheet" />
      </head>
      <body className="grain min-h-screen">
        {children}
      </body>
    </html>
  )
}
