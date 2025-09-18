"use client"

import { useTheme } from "next-themes"
import { Toaster as Sonner, ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      richColors
      className="toaster group"
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          // success / error
          "--toast-success-bg": "oklch(0.75 0.12 160)",
          "--toast-success-fg": "white",
          "--toast-error-bg": "oklch(0.63 0.17 25)",
          "--toast-error-fg": "white",
          "--toast-info-bg": "oklch(0.75 0.08 240)",
          "--toast-info-fg": "white",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
