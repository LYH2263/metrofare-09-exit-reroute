<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'

const items = ref([])
const stations = ref([])
const error = ref('')
const openId = ref(null)
const detail = ref(null)
const choice = ref({})

const load = async () => { items.value = (await getJSON('/api/history')).items }

onMounted(async () => {
  await load()
  stations.value = (await getJSON('/api/stations')).items
})

const fmtPath = (p) => (p && p.length ? p.join(' → ') : '—')

const toggle = async (id) => {
  if (openId.value === id) { openId.value = null; detail.value = null; return }
  openId.value = id
  detail.value = await getJSON(`/api/history/${id}`)
}

const reroute = async (h) => {
  error.value = ''
  const end = choice.value[h.id]
  if (!end) { error.value = `请先为 #${h.id} 选择新终点`; return }
  try {
    await postJSON(`/api/quote/${h.id}/reroute`, { end })
    choice.value[h.id] = ''
    await load()
  } catch (e) {
    error.value = `#${h.id} 改终点失败:${e.message}`
  }
}
</script>
<template>
  <div class="page"><h1>试算记录</h1>
    <p v-if="error" class="err">{{ error }}</p>
    <table>
      <tr><th>#</th><th>时间</th><th>起 → 终</th><th>途经站</th><th>站数</th><th>票价</th><th>来源</th><th>改终点</th></tr>
      <template v-for="h in items" :key="h.id">
        <tr>
          <td><a href="#" @click.prevent="toggle(h.id)">#{{ h.id }}</a></td>
          <td>{{ h.created_at }}</td>
          <td>{{ h.start }} → {{ h.end }}</td>
          <td>{{ fmtPath(h.path) }}</td>
          <td>{{ h.hops ?? '—' }}</td>
          <td>{{ h.fare != null ? '¥' + h.fare : '不可达' }}</td>
          <td>
            <span v-if="h.parent_id">改自 <a href="#" @click.prevent="toggle(h.parent_id)">#{{ h.parent_id }}</a></span>
            <span v-else class="muted">原始</span>
          </td>
          <td class="reroute-cell">
            <template v-if="h.reachable">
              <select v-model="choice[h.id]">
                <option value="" disabled>新终点</option>
                <option v-for="s in stations" :key="s.code" :value="s.code">{{ s.name }}({{ s.code }})</option>
              </select>
              <button @click="reroute(h)">重寻路</button>
            </template>
            <span v-else class="muted">不可达</span>
          </td>
        </tr>
        <tr v-if="openId === h.id && detail" class="detail-row">
          <td colspan="8">
            #{{ detail.id }} · {{ detail.start }} → {{ detail.end }} ·
            途经 {{ fmtPath(detail.path) }} · 站数 {{ detail.hops }} · 票价 ¥{{ detail.fare }}
            <span v-if="detail.parent_id"> · 改自 #{{ detail.parent_id }}</span>
          </td>
        </tr>
      </template>
    </table>
  </div>
</template>
