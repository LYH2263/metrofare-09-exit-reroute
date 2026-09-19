<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'

const items = ref([])
const stations = ref([])
const pick = ref({})
const error = ref('')
const busy = ref(false)

const load = async () => { items.value = (await getJSON('/api/history')).items }
onMounted(async () => {
  await load()
  stations.value = (await getJSON('/api/stations')).items
})

const pathOf = (h) => (h.result && h.result.path ? h.result.path.join(' → ') : '—')
const refOf = (h) => (h.input && h.input.reroute_of) || (h.result && h.result.reroute_of) || null

const reroute = async (h) => {
  error.value = ''
  const end = pick.value[h.id]
  if (!end) { error.value = `记录 #${h.id}：请先选择新终点`; return }
  busy.value = true
  try {
    await postJSON(`/api/quote/${h.id}/reroute`, { end })
    await load()
  } catch (e) {
    error.value = `记录 #${h.id} 改终点失败：${e.message}`
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page"><h1>试算记录</h1>
    <p v-if="error" class="err">{{ error }}</p>
    <table>
      <tr><th>编号</th><th>时间</th><th>起 → 终</th><th>站数</th><th>票价</th><th>途经站</th><th>来源</th><th>改终点</th></tr>
      <tr v-for="h in items" :key="h.id">
        <td><router-link :to="`/history/${h.id}`">#{{ h.id }}</router-link></td>
        <td>{{ h.created_at }}</td>
        <td>{{ h.input.start }} → {{ h.input.end }}</td>
        <td>{{ h.result.hops ?? '—' }}</td>
        <td>{{ h.result.fare != null ? `¥${h.result.fare}` : '—' }}</td>
        <td>{{ pathOf(h) }}</td>
        <td>
          <router-link v-if="refOf(h)" :to="`/history/${refOf(h)}`">#{{ refOf(h) }}</router-link>
          <span v-else class="muted">原始</span>
        </td>
        <td>
          <template v-if="h.result && h.result.reachable">
            <select v-model="pick[h.id]">
              <option disabled value="">新终点</option>
              <option v-for="s in stations" :key="s.code" :value="s.code">{{ s.name }}</option>
            </select>
            <button :disabled="busy" @click="reroute(h)">重寻路</button>
          </template>
          <span v-else class="muted">不可达</span>
        </td>
      </tr>
    </table>
  </div>
</template>
