<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getJSON } from '../api'

const route = useRoute()
const rec = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    rec.value = await getJSON(`/api/history/${route.params.id}`)
  } catch {
    error.value = '记录不存在'
  }
})
</script>

<template>
  <div class="page"><h1>记录 #{{ route.params.id }}</h1>
    <p v-if="error" class="err">{{ error }}</p>
    <div v-if="rec" class="panel">
      <p>时间：{{ rec.created_at }}</p>
      <p>起点：{{ rec.input.start }} · 终点：{{ rec.input.end }}</p>
      <p v-if="rec.result.reachable">站数 {{ rec.result.hops }} · 票价 <span class="hero-num">¥{{ rec.result.fare }}</span></p>
      <p v-else class="muted">不可达</p>
      <p>途经站：{{ rec.result.path ? rec.result.path.join(' → ') : '—' }}</p>
      <p v-if="rec.input.reroute_of">
        来源：改终点自 <router-link :to="`/history/${rec.input.reroute_of}`">#{{ rec.input.reroute_of }}</router-link>
      </p>
    </div>
    <p><router-link to="/history">返回记录</router-link></p>
  </div>
</template>
