import "@workspace/ui/globals.css"
import { Roboto_Condensed } from "next/font/google"
import { ThemeProvider } from "@/components/theme-provider"

const robotoCondensed = Roboto_Condensed({
  subsets: ["latin"],
  variable: "--font-roboto-condensed",
  display: "swap",
})

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning className={`antialiased ${robotoCondensed.variable}`}>
      <body className="font-[family-name:var(--font-roboto-condensed)]">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  )
}
