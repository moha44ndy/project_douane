import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mosam - Classification CEDEAO",
  description: "Assistant de classification tarifaire CEDEAO",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className="bg-surface text-foreground min-h-screen">
        <div className="min-h-screen bg-gradient">
          <main className="max-w-6xl mx-auto px-4 py-10">{children}</main>
        </div>
      </body>
    </html>
  );
}

