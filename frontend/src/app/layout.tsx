import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mosam - Classification CEDEAO",
  description: "Assistant de classification tarifaire CEDEAO",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className="text-foreground min-h-screen">
        <div className="min-h-screen bg-gradient">
          <main className="main-shell">{children}</main>
        </div>
      </body>
    </html>
  );
}

