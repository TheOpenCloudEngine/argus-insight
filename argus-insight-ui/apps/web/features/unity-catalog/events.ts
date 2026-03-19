/**
 * Custom event for signaling Unity Catalog data changes.
 *
 * Components can dispatch this event after mutations (create, delete, update)
 * and listeners (e.g. Schema Browser) will refresh their data.
 */

const UC_REFRESH_EVENT = "uc:refresh"

export function dispatchUcRefresh() {
  window.dispatchEvent(new CustomEvent(UC_REFRESH_EVENT))
}

export function useUcRefreshListener(callback: () => void) {
  // This is intentionally not a hook body – call from useEffect
  return { event: UC_REFRESH_EVENT, callback }
}

export { UC_REFRESH_EVENT }
