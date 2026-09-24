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

export type ApiError = {
  status: number
  message: string
  fields?: string[]
}

/** 从失败响应里取可读说明：兼容 {detail:{message,fields}}、{detail:"文本"} 与网络异常。 */
export async function readError(response: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  const detail = (body as { detail?: unknown } | null)?.detail
  if (detail && typeof detail === 'object') {
    const info = detail as { message?: unknown; fields?: unknown }
    if (typeof info.message === 'string') {
      return {
        status: response.status,
        message: info.message,
        fields: Array.isArray(info.fields) ? (info.fields as string[]) : undefined,
      }
    }
  }
  if (typeof detail === 'string' && detail) {
    return { status: response.status, message: detail }
  }
  return { status: response.status, message: `接口返回 ${response.status}，本次操作未生效` }
}

/** 生成本次提交的幂等键；同一键的重复请求后端只会处理一次。 */
export function newRequestId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2)}`
}
