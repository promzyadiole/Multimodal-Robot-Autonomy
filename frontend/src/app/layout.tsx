import "./globals.css";
import type { Metadata } from "next";
import { Archivo, Instrument_Serif, JetBrains_Mono } from "next/font/google";
import Shell from "@/components/shell";

// Editorial serif against instrument mono: the serif carries research
// gravitas, the mono keeps the telemetry honest to the domain.
const instrument = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument",
  display: "swap",
});

const archivo = Archivo({
  subsets: ["latin"],
  variable: "--font-archivo",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Language-Grounded Robot Autonomy",
  description:
    "A custom differential-drive robot that takes destinations in plain language — LLM intent grounding, multimodal perception, and ROS 2 navigation.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${instrument.variable} ${archivo.variable} ${jetbrains.variable}`}
    >
      <body className="min-h-screen bg-ground text-ink">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
