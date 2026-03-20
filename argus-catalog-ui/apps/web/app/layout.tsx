import "@workspace/ui/globals.css"
import localFont from "next/font/local"
import { Toaster } from "sonner"
import { ThemeProvider } from "@/components/theme-provider"

const robotoCondensed = localFont({
  src: "./fonts/RobotoCondensed-Variable.ttf",
  variable: "--font-roboto-condensed",
  display: "swap",
})

const d2coding = localFont({
  src: [
    { path: "./fonts/D2Coding-Regular.ttf", weight: "400", style: "normal" },
    { path: "./fonts/D2Coding-Bold.ttf", weight: "700", style: "normal" },
  ],
  variable: "--font-d2coding",
  display: "swap",
})

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`antialiased ${robotoCondensed.variable} ${d2coding.variable}`}
    >
      <body className="font-[family-name:var(--font-roboto-condensed)]">
        <ThemeProvider>
          {children}
          <Toaster richColors position="top-center" />
        </ThemeProvider>
      </body>
    </html>
  )
}
