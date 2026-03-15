import { useState } from "react"

/**
 * Custom hook for dialog state management
 * @param initialState string | null
 * @returns A stateful value, and a function to update it.
 * @example const [open, setOpen] = useDialogState<"add" | "edit" | "delete">()
 */
export default function useDialogState<T extends string | boolean>(
  initialState: T | null = null
) {
  const [open, _setOpen] = useState<T | null>(initialState)

  const setOpen = (str: T | null) =>
    _setOpen((prev) => (prev === str ? null : str))

  return [open, setOpen] as const
}
