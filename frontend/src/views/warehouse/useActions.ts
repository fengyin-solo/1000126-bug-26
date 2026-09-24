import { ref } from 'vue'

import { newRequestId, readError, request } from '@/api/client'

export const ENDPOINT = '/api/warehouse'

export const columns = ["冷库编码", "冷库名称", "库区温区", "设定温度", "库容吨位", "责任人", "启用状态"]
export const actions = ["启用冷库", "安排检修", "停用冷库"]
export const statuses = ["已启用", "检修中", "已停用"]

export type Row = Record<string, string | number | null>

export type ActionLog = {
  id: number
  entry_id: number
  action: string
  from_status: string
  to_status: string
  request_id: string | null
  message: string
  operated_at: string
}

export type Detail = Row & { 动作留痕?: ActionLog[] }

/** 正在执行的动作键，用于禁用按钮，防止一次点击被重复提交。 */
export const submittingKey = ref('')

export type SubmitOptions = {
  /** 成功后刷新页面数据 */
  onSuccess?: () => void
  /** 把失败说明回传给页面展示，并保留重试入口 */
  onError?: (message: string) => void
}

/**
 * 提交冷库动作：
 * - 每次业务提交都带 request_id，后端按幂等键去重，重复提交不会残留第二条记录；
 * - 网络未送达时可用同一 request_id 重试，不会重复落地；
 * - 业务被拦下时读后端的可读说明，交给页面展示并允许重新发起。
 */
export async function submitAction(
  action: string,
  row: Row,
  options: SubmitOptions = {},
): Promise<void> {
  const key = `${row.id}:${action}`
  if (submittingKey.value) {
    return
  }
  submittingKey.value = key
  let requestId = newRequestId()
  const send = async (): Promise<boolean> => {
    try {
      const response = await request(`${ENDPOINT}/${row.id}/actions`, {
        method: 'POST',
        body: JSON.stringify({ values: { action, request_id: requestId } }),
      })
      if (response.ok) {
        return true
      }
      const info = await readError(response)
      options.onError?.(info.message)
      // 业务被拦下（如冷库正在作业）：下次重试是一次新的业务判断，换新幂等键。
      if (response.status === 409) {
        requestId = newRequestId()
      }
      return false
    } catch (error) {
      options.onError?.(error instanceof Error ? error.message : '接口未送达，请检查网络后重试')
      return false
    }
  }
  try {
    if (await send()) {
      options.onSuccess?.()
    }
  } finally {
    submittingKey.value = ''
  }
}
