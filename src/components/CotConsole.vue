<template>
  <section class="panel console-panel">
    <div class="panel-heading"><div><span class="eyebrow">LIVE TRACE</span><h2>协同运行轨迹</h2></div><span :class="['live-state', isRunning ? 'on' : '']"><i></i>{{ isRunning ? 'RUNNING' : 'IDLE' }}</span></div>
    <div class="trace-list" ref="consoleRef">
      <div v-for="(log, index) in logs" :key="index" :class="['trace-item', log.kind || 'log']">
        <div class="trace-time">{{ log.time }}</div><div class="trace-marker"></div><div class="trace-body"><strong>{{ log.agent || log.title }}</strong><p>{{ log.content }}</p><small v-if="log.meta">{{ log.meta }}</small></div>
      </div>
      <div v-if="!logs.length" class="empty-state"><span class="empty-icon">◌</span><p>输入业务目标，启动一次自主编排</p><small>系统会把每个决策和工具调用记录在这里</small></div>
    </div>
  </section>
</template>
<script setup>
import { ref, watch, nextTick } from 'vue';
const props = defineProps({ logs: { type: Array, default: () => [] }, isRunning: Boolean });
const consoleRef = ref(null);
watch(() => props.logs, async () => { await nextTick(); if (consoleRef.value) consoleRef.value.scrollTop = consoleRef.value.scrollHeight; }, { deep: true });
</script>
