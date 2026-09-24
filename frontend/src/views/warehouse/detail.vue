<template>
  <section class="page" data-module="warehouse-detail">
    <header class="page-head">
      <div>
        <h2>冷库档案明细</h2>
        <p class="page-desc">
          <router-link class="back-link" to="/warehouse">← 返回冷库管理列表</router-link>
        </p>
      </div>
    </header>

    <div v-if="notFound" class="inline-error">
      <span>{{ notFound }}</span>
      <button class="btn" type="button" @click="loadDetail">重新加载</button>
      <router-link class="btn" to="/warehouse">返回列表</router-link>
    </div>

    <template v-else-if="entry">
      <div v-if="actionError" class="inline-error">
        <span>{{ actionError.message }}</span>
        <button class="btn" type="button" @click="retryAction">重试</button>
        <button class="btn ghost" type="button" @click="actionError = null">知道了</button>
      </div>

      <div class="detail-layout">
        <div class="detail-main">
          <div class="stat-row">
            <article class="stat-card">
              <span class="stat-label">当前状态</span>
              <strong class="stat-value">{{ entry.status ?? '—' }}</strong>
            </article>
            <article class="stat-card">
              <span class="stat-label">责任人</span>
              <strong class="stat-value">{{ entry['责任人'] ?? '—' }}</strong>
            </article>
            <article class="stat-card">
              <span class="stat-label">库区温区</span>
              <strong class="stat-value">{{ entry['库区温区'] ?? '—' }}</strong>
            </article>
          </div>

          <table class="data-table">
            <tbody>
              <tr v-for="field in profileFields" :key="field">
                <th style="width: 140px">{{ field }}</th>
                <td>{{ entry[field] ?? '—' }}</td>
              </tr>
            </tbody>
          </table>

          <div style="margin-top: 12px; display: flex; gap: 8px">
            <button
              v-for="action in actions"
              :key="action"
              class="btn"
              :class="{ primary: action === '停用冷库' }"
              type="button"
              :disabled="submittingKey === `${entry.id}:${action}`"
              @click="runAction(action)"
            >
              {{ submittingKey === `${entry.id}:${action}` ? `${action}中…` : action }}
            </button>
          </div>
          <p class="page-desc" style="margin-top: 8px">
            作业中的冷库需先「安排检修」，检修通过后才能「停用冷库」；被拦下时上方会给出原因，可直接重试。
          </p>
        </div>

        <aside class="detail-side">
          <div class="side-card">
            <h3>动作留痕</h3>
            <ul v-if="logs.length" class="log-list">
              <li v-for="log in logs" :key="log.id" class="log-item">
                <div><strong>{{ log.action }}</strong>：{{ log.from_status }} → {{ log.to_status }}</div>
                <div class="log-time">{{ log.operated_at }}</div>
              </li>
            </ul>
            <p v-else class="page-desc">暂无动作记录，停用、检修等操作成功后会在此留痕；重复提交不会产生重复记录。</p>
          </div>
        </aside>
      </div>
    </template>

    <div v-else-if="loadError" class="inline-error">
      <span>{{ loadError }}</span>
      <button class="btn" type="button" @click="loadDetail">重新加载</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { readError, request } from '@/api/client'
import { actions, ActionLog, Detail, ENDPOINT, Row, submittingKey, submitAction } from './useActions'

const route = useRoute()
const entry = ref<Detail | null>(null)
const logs = ref<ActionLog[]>([])
const loadError = ref('')
const notFound = ref('')
const actionError = ref<{ message: string; target: string } | null>(null)

const profileFields = ["冷库编码", "冷库名称", "库区温区", "设定温度", "库容吨位", "责任人", "启用状态"]

function entryId(): number {
  return Number(route.params.id)
}

async function loadDetail() {
  loadError.value = ''
  notFound.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId()}`)
    if (!response.ok) {
      const info = await readError(response)
      if (response.status === 404) {
        notFound.value = info.message
      } else {
        loadError.value = info.message
      }
      return
    }
    const payload = (await response.json()) as Detail
    entry.value = payload
    logs.value = payload.动作留痕 ?? []
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '冷库档案明细读取失败'
  }
}

function runAction(action: string) {
  if (!entry.value) {
    return
  }
  actionError.value = null
  const row: Row = entry.value
  void submitAction(action, row, {
    onSuccess: () => loadDetail(),
    onError: (message) => {
      actionError.value = { message, target: action }
    },
  })
}

function retryAction() {
  if (actionError.value) {
    runAction(actionError.value.target)
  }
}

onMounted(loadDetail)
</script>
