<template>
  <section class="page" data-module="warehouse">
    <header class="page-head">
      <div>
        <h2>冷库管理管理</h2>
        <p class="page-desc">维护冷库档案，围绕冷库编码、冷库名称、库区温区、设定温度做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记冷库档案</button>
        <button class="btn" type="button" @click="exportRows">导出冷库管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <!-- 列表读取失败：给出说明与重试入口 -->
    <div v-if="listError" class="inline-feedback error">
      <span>{{ listError }}</span>
      <button class="btn small" type="button" @click="reload">重试加载</button>
    </div>

    <table v-else class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <RouterLink v-if="column === '冷库编码'" class="link" :to="`/warehouse/${row.id}`">
              {{ row[column] ?? '—' }}
            </RouterLink>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="pendingKey === actionKey(action, row)"
              @click="runAction(action, row)"
            >
              {{ pendingKey === actionKey(action, row) ? '提交中…' : action }}
            </button>
            <!-- 单行失败说明 + 仅重试该动作 -->
            <span v-if="actionErrors[Number(row.id)]" class="row-error">
              {{ actionErrors[Number(row.id)] }}
              <button
                class="link"
                type="button"
                @click="runAction(failedAction[Number(row.id)], row)"
              >重试</button>
            </span>
          </td>
        </tr>
        <tr v-if="!loading && !rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            暂无冷库管理数据，可先登记冷库档案
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条冷库管理记录</span>
      <span v-if="listError" class="error-text">列表暂不可用，卡片按 0 展示</span>
    </footer>

    <!-- 登记冷库档案：参数为空在提交前拦下，提交失败保留填写内容并允许重试 -->
    <div v-if="createOpen" class="modal-mask" @click.self="closeCreate">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>登记冷库档案</h3>
        <p class="page-desc">冷库编码、冷库名称、库区温区为必填项，参数为空将无法保存。</p>
        <label v-for="field in createFields" :key="field.key" class="form-item">
          <span>{{ field.label }}{{ field.required ? ' *' : '' }}</span>
          <input v-model="createForm[field.key]" :placeholder="`请输入${field.label}`" />
        </label>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="submit" :disabled="creating">
            {{ creating ? '提交中…' : '保存档案' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { createToken, postAction, request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/warehouse'
const columns = ['冷库编码', '冷库名称', '库区温区', '设定温度', '库容吨位', '责任人', '启用状态']
const actions = ['启用冷库', '安排检修', '停用冷库']
const filterFields = columns.slice(0, 3)

// 卡片始终渲染：没有数据或加载失败时展示零值，而不是留白
const stats = ref([
  { label: '启用冷库', value: 0 },
  { label: '检修冷库', value: 0 },
  { label: '库容利用率', value: '0%' },
])

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const listError = ref('')
const filters = ref<Record<string, string>>({})

// 动作提交状态：正在提交的行禁用按钮；失败只在对应行提示并保留重试入口
const pendingKey = ref('')
const actionErrors = reactive<Record<number, string>>({})
const failedAction = reactive<Record<number, string>>({})
// 每次点击动作生成一个令牌，失败重试沿用同一令牌，保证重复提交服务端只生效一次
const failedToken = reactive<Record<number, string>>({})

// 登记表单
const createFields = [
  { key: '冷库编码', label: '冷库编码', required: true },
  { key: '冷库名称', label: '冷库名称', required: true },
  { key: '库区温区', label: '库区温区', required: true },
  { key: '设定温度', label: '设定温度', required: false },
  { key: '库容吨位', label: '库容吨位', required: false },
  { key: '责任人', label: '责任人', required: false },
] as const
const emptyForm = (): Record<string, string> => ({
  冷库编码: '',
  冷库名称: '',
  库区温区: '',
  设定温度: '',
  库容吨位: '',
  责任人: '',
})
const createOpen = ref(false)
const createForm = ref<Record<string, string>>(emptyForm())
const creating = ref(false)
const createError = ref('')
// 一次登记一个令牌：失败重试沿用同一令牌，成功后再次打开换新令牌，天然防重复落库
let createTokenValue = ''

function actionKey(action: string, row: Row) {
  return `${row.id}:${action}`
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = emptyForm()
  createError.value = ''
  createTokenValue = createToken()
  createOpen.value = true
}

function closeCreate() {
  if (creating.value) {
    return
  }
  createOpen.value = false
}

async function submitCreate() {
  createError.value = ''
  // 参数为空：提交前兜底提示，明确指出缺哪一项，避免点保存没反应
  const missing = createFields
    .filter((field) => field.required && !createForm.value[field.key].trim())
    .map((field) => field.label)
  if (missing.length) {
    createError.value = `缺少必填项：${missing.join('、')}，请补全后再保存`
    return
  }
  creating.value = true
  try {
    const result = await postAction(ENDPOINT, { ...createForm.value }, createTokenValue)
    if (!result.ok) {
      // 业务失败（如编码重复）：保留已填内容，给出说明并允许原地重试
      createError.value = result.message || '冷库档案未保存成功，请稍后重试'
      return
    }
    createOpen.value = false
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '冷库档案提交失败，请稍后重试'
  } finally {
    creating.value = false
  }
}

async function runAction(action: string, row: Row) {
  const rowId = Number(row.id)
  pendingKey.value = actionKey(action, row)
  // 失败重试沿用上次的令牌；首次执行或换动作时生成新令牌
  const token = failedAction[rowId] === action ? failedToken[rowId] : createToken()
  delete actionErrors[rowId]
  delete failedAction[rowId]
  delete failedToken[rowId]
  try {
    const result = await postAction(`${ENDPOINT}/${row.id}/actions`, { action }, token)
    // 不能只看 HTTP 状态：停用正在作业的冷库接口返回 ok=false，必须按业务结果提示
    if (!result.ok) {
      actionErrors[rowId] = result.message || '冷库管理动作未生效'
      failedAction[rowId] = action
      failedToken[rowId] = token
      return
    }
    await reload()
  } catch (error) {
    actionErrors[rowId] = error instanceof Error ? error.message : '冷库管理操作失败，请稍后重试'
    failedAction[rowId] = action
    failedToken[rowId] = token
  } finally {
    pendingKey.value = ''
  }
}

function refreshStats(items: Row[]) {
  const active = items.filter((row) => row.status === '已启用').length
  const repairing = items.filter((row) => row.status === '检修中').length
  // 库容吨位字段多为文本，能解析为数字时才计算利用率，否则按 0% 兜底
  const tonnage = items
    .map((row) => Number(row['库容吨位']))
    .filter((value) => Number.isFinite(value) && value > 0)
  const utilization = tonnage.length ? `${Math.round((tonnage.length / items.length) * 100)}%` : '0%'
  stats.value = [
    { label: '启用冷库', value: active },
    { label: '检修冷库', value: repairing },
    { label: '库容利用率', value: items.length ? utilization : '0%' },
  ]
}

async function reload() {
  loading.value = true
  listError.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error(`冷库档案列表读取失败（${response.status}）`)
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    refreshStats(rows.value)
  } catch (error) {
    listError.value = error instanceof Error ? error.message : '冷库管理列表读取失败'
    // 失败时卡片给零值，不留白
    refreshStats([])
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>
