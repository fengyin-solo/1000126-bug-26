<template>
  <section class="page" data-module="warehouse-detail">
    <header class="page-head">
      <div>
        <h2>冷库档案详情</h2>
        <p class="page-desc">查看冷库档案完整信息，并在本页直接执行启用、检修、停用流转。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/warehouse">返回列表</RouterLink>
      </div>
    </header>

    <!-- 明细读取失败：说明原因并提供重试，不让页面留白 -->
    <div v-if="loadError && !notFound" class="inline-feedback error">
      <span>{{ loadError }}</span>
      <button class="btn small" type="button" @click="loadDetail()">重新加载</button>
    </div>
    <!-- 档案不存在（已归档）：给出说明与返回入口 -->
    <div v-else-if="loadError && notFound" class="inline-feedback">
      <span>{{ loadError }}</span>
      <RouterLink class="btn small" to="/warehouse">回到列表</RouterLink>
    </div>

    <div v-else-if="loading" class="inline-feedback">
      <span>档案加载中…</span>
    </div>

    <template v-else-if="entry">
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">当前状态</span>
          <strong class="stat-value">{{ entry.status ?? '—' }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">待处理</span>
          <strong class="stat-value">{{ entry.pending ? '是' : '否' }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">异常标记</span>
          <strong class="stat-value">{{ entry.abnormal ? '是' : '否' }}</strong>
        </article>
      </div>

      <table class="data-table detail-table">
        <tbody>
          <tr v-for="field in detailFields" :key="field">
            <th>{{ field }}</th>
            <td>{{ entry[field] ?? '—' }}</td>
          </tr>
        </tbody>
      </table>

      <div class="action-bar">
        <button
          v-for="action in actions"
          :key="action"
          class="btn"
          :class="{ primary: action === '停用冷库' }"
          type="button"
          :disabled="pendingAction !== ''"
          @click="runAction(action)"
        >
          {{ pendingAction === action ? '提交中…' : action }}
        </button>
      </div>

      <!-- 动作失败（含正在作业被拦）：就地说明并提供重试入口 -->
      <div v-if="actionError" class="inline-feedback error">
        <span>{{ actionError }}</span>
        <button class="btn small" type="button" @click="runAction(lastAction)">重试该操作</button>
      </div>
      <p v-if="actionOk" class="ok-text">{{ actionOk }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { createToken, postAction, request } from '@/api/client'

type Entry = Record<string, string | number | boolean | null>

const route = useRoute()
const ENDPOINT = '/api/warehouse'
const actions = ['启用冷库', '安排检修', '停用冷库']
const detailFields = ['冷库编码', '冷库名称', '库区温区', '设定温度', '库容吨位', '责任人', '启用状态']

const entry = ref<Entry | null>(null)
const loading = ref(false)
const loadError = ref('')
const notFound = ref(false)
const pendingAction = ref('')
const actionError = ref('')
const actionOk = ref('')
const lastAction = ref('')
// 失败重试沿用同一令牌，保证重复提交在服务端只生效一次
let actionToken = ''

async function loadDetail(options: { keepFeedback?: boolean } = {}) {
  const id = Number(route.params.id)
  loading.value = true
  if (!options.keepFeedback) {
    loadError.value = ''
    actionError.value = ''
    actionOk.value = ''
  }
  notFound.value = false
  try {
    const response = await request(`${ENDPOINT}/${id}`)
    if (response.status === 404) {
      let detail = `冷库档案 ${id} 不存在或已归档`
      try {
        detail = ((await response.json()) as { detail?: string }).detail ?? detail
      } catch {
        // 沿用默认说明
      }
      entry.value = null
      loadError.value = detail
      notFound.value = true
      return
    }
    if (!response.ok) {
      throw new Error(`冷库档案读取失败（${response.status}），请稍后重试`)
    }
    entry.value = (await response.json()) as Entry
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '冷库档案读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function runAction(action: string) {
  if (!entry.value) {
    return
  }
  const id = Number(route.params.id)
  // 提交锁：请求未返回前禁用所有动作按钮，杜绝重复提交
  pendingAction.value = action
  // 仅“同一动作失败后的重试”沿用旧令牌；首次执行或换动作都换新令牌
  const isRetry = actionError.value !== '' && lastAction.value === action
  lastAction.value = action
  if (!isRetry) {
    actionToken = createToken()
  }
  actionError.value = ''
  actionOk.value = ''
  try {
    const result = await postAction(`${ENDPOINT}/${id}/actions`, { action }, actionToken)
    // 必须按业务 ok 判断：HTTP 200 但 ok=false 表示被业务规则拦下（如作业中停用）
    if (!result.ok) {
      actionError.value = result.message || '冷库管理动作未生效，请稍后重试'
      return
    }
    actionOk.value = result.message || '操作已生效'
    // 刷新档案但保留成功提示
    await loadDetail({ keepFeedback: true })
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : '冷库管理操作失败，请稍后重试'
  } finally {
    pendingAction.value = ''
  }
}

onMounted(() => loadDetail())
</script>
