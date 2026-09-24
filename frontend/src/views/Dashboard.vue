<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>

    <!-- 概览读取失败：卡片用零值兜底不留白，并给出说明与重试入口 -->
    <div v-if="loadError" class="inline-feedback error">
      <span>{{ loadError }}</span>
      <button class="btn small" type="button" :disabled="loading" @click="loadOverview">
        {{ loading ? '加载中…' : '重试加载' }}
      </button>
    </div>

    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
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
        <tr v-if="!loading && !moduleRows.length">
          <td colspan="4" class="empty-state">暂无模块数据，指标按零值展示</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const EMPTY_CARDS: Overview['cards'] = [
  { label: '业务模块', value: 0 },
  { label: '今日新增', value: 0 },
  { label: '待处理', value: 0 },
  { label: '异常量', value: 0 },
]

const cards = ref<Overview['cards']>(EMPTY_CARDS.map((card) => ({ ...card })))
const moduleRows = ref<Overview['modules']>([])
const loadError = ref('')
const loading = ref(false)

async function loadOverview() {
  loading.value = true
  loadError.value = ''
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    // 接口缺卡或数量不足时用零值补齐，保证四张卡片位置不留白
    cards.value = EMPTY_CARDS.map((empty) => {
      const remote = payload.cards?.find((card) => card.label === empty.label)
      return remote ?? empty
    })
    moduleRows.value = payload.modules ?? []
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '运营概览读取失败'
    // 兜底：失败也展示零值卡片与空表，而不是留白
    cards.value = EMPTY_CARDS.map((card) => ({ ...card }))
    moduleRows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadOverview)
</script>
