/** 统一请求封装：拼后端地址、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}

/** 动作接口统一返回 { ok, message, entry }：HTTP 200 但 ok=false 也算失败。 */
export type ActionResponse = {
  ok: boolean
  message: string
  entry?: Record<string, unknown> | null
}

export async function postAction(
  path: string,
  values: Record<string, unknown>,
  clientToken?: string,
): Promise<ActionResponse> {
  const response = await request(path, {
    method: 'POST',
    body: JSON.stringify({ values, client_token: clientToken ?? createToken() }),
  })
  if (!response.ok) {
    let detail = `接口返回 ${response.status}`
    try {
      const errorBody = (await response.json()) as { detail?: string }
      if (errorBody.detail) {
        detail = errorBody.detail
      }
    } catch {
      // 非 JSON 错误体时保留状态码说明
    }
    throw new Error(`${detail}，请稍后重试`)
  }
  return (await response.json()) as ActionResponse
}

/** 生成一次性提交令牌：同一令牌在服务端窗口内只会生效一次，防止重复提交落两条记录。 */
export function createToken(): string {
  const random = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${Date.now().toString(36)}-${random}`
}
