import type { MenuConfig } from "@/types/menu"

/**
 * 메뉴 설정을 반환합니다.
 *
 * 현재는 로컬 JSON 파일에서 읽어오며,
 * 향후 NEXT_PUBLIC_API_URL 환경 변수를 설정하면 /api/menu 엔드포인트에서 가져옵니다.
 */
export async function getMenu(): Promise<MenuConfig> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  if (apiUrl) {
    const res = await fetch(`${apiUrl}/api/menu`, {
      next: { revalidate: 60 }, // 60초 캐시
    })

    if (!res.ok) {
      throw new Error(`Failed to fetch menu: ${res.status}`)
    }

    return res.json() as Promise<MenuConfig>
  }

  // fallback: 로컬 JSON
  const data = await import("@/data/menu.json")
  return data.default as MenuConfig
}
