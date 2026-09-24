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

    <div v-if="loadError" class="inline-error">
      <span>{{ loadError }}</span>
      <button class="btn" type="button" @click="reload">重新加载</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <router-link v-if="column === '冷库编码'" class="link" :to="`/warehouse/${row.id}`">
              {{ row[column] ?? '—' }}
            </router-link>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <span v-for="action in actions" :key="action">
              <button
                class="link"
                type="button"
                :disabled="submittingKey === `${row.id}:${action}`"
                @click="runAction(action, row)"
              >
                {{ submittingKey === `${row.id}:${action}` ? `${action}中…` : action }}
              </button>
            </span>
          </td>
        </tr>
        <tr v-if="!rows.length && !loadError">
          <td :colspan="columns.length + 1" class="empty-state">
            暂无冷库管理数据，可先
            <button class="retry-btn" type="button" @click="openCreate">登记冷库档案</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 行内动作失败说明：给出原因与重试入口 -->
    <div v-if="actionError" class="inline-error">
      <span>{{ actionError.message }}</span>
      <button class="btn" type="button" @click="retryAction">重试</button>
      <button class="btn ghost" type="button" @click="actionError = null">知道了</button>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条冷库管理记录</span>
      <span v-if="actionError" class="error-text">{{ actionError.target }}（冷库 #{{ actionError.row.id }}）操作未生效</span>
    </footer>

    <!-- 登记冷库档案 -->
    <div v-if="createOpen" class="modal-mask" @click.self="closeCreate">
      <div class="modal-card">
        <h3 class="modal-title">登记冷库档案</h3>
        <p class="modal-desc">带 * 为必填项，参数不完整时不会保存，并会指出缺哪一项。</p>
        <form @submit.prevent="submitCreate">
          <div class="form-grid">
            <div v-for="field in formFields" :key="field.key" class="form-field" :class="{ wide: field.wide }">
              <label :class="{ required: field.required }">{{ field.label }}</label>
              <input
                v-model="form[field.key]"
                :class="{ invalid: createMissing.includes(field.key) }"
                :placeholder="field.placeholder"
              />
            </div>
          </div>
          <p v-if="createError" class="form-error">{{ createError }}</p>
          <div class="modal-actions">
            <button class="btn ghost" type="button" :disabled="creating" @click="closeCreate">取消</button>
            <button class="btn primary" type="submit" :disabled="creating">
              {{ creating ? '保存中…' : '保存档案' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { newRequestId, readError, request } from '@/api/client'
import { actions, columns, ENDPOINT, Row, statuses, submittingKey, submitAction } from './useActions'

const rows = ref<Row[]>([])
const total = ref(0)
const loadError = ref('')
const actionError = ref<{ message: string; target: string; row: Row } | null>(null)
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

// 概览卡片没有数据时也显示零值，不留白
const stats = ref([
  { label: '启用冷库', value: 0 },
  { label: '检修冷库', value: 0 },
  { label: '已停用', value: 0 },
])

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  loadError.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      const info = await readError(response)
      throw new Error(info.message)
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    // 卡片按当前列表实际状态计数；列表为空时自然为 0。
    stats.value[0].value = rows.value.filter((row) => row.status === statuses[0]).length
    stats.value[1].value = rows.value.filter((row) => row.status === statuses[1]).length
    stats.value[2].value = rows.value.filter((row) => row.status === statuses[2]).length
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '冷库档案列表读取失败'
  }
}

function runAction(action: string, row: Row) {
  actionError.value = null
  void submitAction(action, row, {
    onSuccess: () => reload(),
    onError: (message) => {
      actionError.value = { message, target: action, row }
    },
  })
}

function retryAction() {
  if (!actionError.value) {
    return
  }
  const { target, row } = actionError.value
  void runAction(target, row)
}

// ---- 登记冷库档案 ----
const formFields = [
  { key: '冷库编码', label: '冷库编码', required: true, wide: false, placeholder: '如 WARE-0010' },
  { key: '冷库名称', label: '冷库名称', required: true, wide: false, placeholder: '如 一号冷冻库' },
  { key: '库区温区', label: '库区温区', required: true, wide: true, placeholder: '如 冷冻区（-18℃ 以下）' },
  { key: '设定温度', label: '设定温度', required: false, wide: false, placeholder: '选填，如 -18℃' },
  { key: '库容吨位', label: '库容吨位', required: false, wide: false, placeholder: '选填，如 500 吨' },
  { key: '责任人', label: '责任人', required: false, wide: true, placeholder: '选填' },
] as const

const emptyForm = (): Record<string, string> => ({
  冷库编码: '', 冷库名称: '', 库区温区: '', 设定温度: '', 库容吨位: '', 责任人: '',
})

const createOpen = ref(false)
const creating = ref(false)
const form = ref<Record<string, string>>(emptyForm())
const createError = ref('')
const createMissing = ref<string[]>([])
let createRequestId = newRequestId()

function openCreate() {
  form.value = emptyForm()
  createError.value = ''
  createMissing.value = []
  createRequestId = newRequestId()
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
  // 前端先兜底：必填项为空时直接说明，不发空请求。
  createMissing.value = formFields
    .filter((field) => field.required && !form.value[field.key].trim())
    .map((field) => field.key)
  if (createMissing.value.length) {
    createError.value = `请补全必填项：${createMissing.value.join('、')}`
    return
  }
  creating.value = true
  try {
    const values: Record<string, string> = {}
    for (const field of formFields) {
      const value = form.value[field.key].trim()
      if (value) {
        values[field.key] = value
      }
    }
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values, request_id: createRequestId }),
    })
    if (!response.ok) {
      const info = await readError(response)
      createMissing.value = info.fields ?? []
      createError.value = info.message
      if (response.status >= 500) {
        createError.value = `${info.message}，请稍后重试（已保留你填写的内容）`
      }
      return
    }
    createOpen.value = false
    await reload()
  } catch (error) {
    // 网络未送达：保留表单内容，允许原地重试（同一幂等键，不会重复建档）。
    createError.value = `${error instanceof Error ? error.message : '保存请求未送达'}，请重试`
  } finally {
    creating.value = false
  }
}

onMounted(reload)
</script>
