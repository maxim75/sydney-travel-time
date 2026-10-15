import type { Metadata } from "next";
import { Barlow, Barlow_Condensed } from "next/font/google";
import Script from "next/script";
import type { ReactNode } from "react";
import "./globals.css";

const barlow = Barlow({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-barlow" });
const barlowCondensed = Barlow_Condensed({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-barlow-condensed" });
const GA_ID = "G-WDYB3WJ819";

export const metadata: Metadata = { title: "Sydney Travel Times" };

export default function RootLayout({ children }: { children: ReactNode }) {
  // The font variables go on <html> so the :root tokens --sans and --cond can resolve them
  return (
    <html lang="en-AU" className={`${barlow.variable} ${barlowCondensed.variable}`}>
      <body>
        {children}
        <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`} strategy="afterInteractive" />
        <Script id="gtag-init" strategy="afterInteractive">
          {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GA_ID}');`}
        </Script>
      </body>
    </html>
  );
}
