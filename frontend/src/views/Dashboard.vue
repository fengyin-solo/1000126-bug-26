<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>

    <div v-if="loadError" class="inline-error">
      <span>{{ loadError }}</span>
      <button class="btn" type="button" @click="loadOverview">重新加载</button>
    </div>

    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
        <tr v-if="!moduleRows.length && !loadError">
          <td colspan="4" class="empty-state">暂无业务数据，各项指标均为 0；登记业务记录后这里会自动汇总。</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

// 没有数据或读取失败时，卡片也保持完整的四项并显示零值，不留白。
const ZERO_CARDS: Overview['cards'] = [
  { label: '业务模块', value: 0 },
  { label: '今日新增', value: 0 },
  { label: '待处理', value: 0 },
  { label: '异常量', value: 0 },
]

const cards = ref<Overview['cards']>(ZERO_CARDS.map((card) => ({ ...card })))
const moduleRows = ref<Overview['modules']>([])
const loadError = ref('')

async function loadOverview() {
  loadError.value = ''
  try {
    const response = await request('/api/overview')
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}，概览数据未更新，当前显示零值`)
    }
    const payload = (await response.json()) as Overview
    // 后端缺项时用零值补齐，保证四张卡片恒在。
    cards.value = ZERO_CARDS.map((zero) => {
      const found = payload.cards?.find((card) => card.label === zero.label)
      return found ? { label: zero.label, value: Number(found.value) || 0 } : { ...zero }
    })
    moduleRows.value = payload.modules ?? []
  } catch (error) {
    cards.value = ZERO_CARDS.map((card) => ({ ...card }))
    loadError.value = error instanceof Error ? error.message : '运营概览读取失败，当前显示零值'
  }
}

onMounted(loadOverview)
</script>
