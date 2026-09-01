<template>
  <div class="agent-dashboard">
    <!-- 顶栏状态与指令下发 -->
    <header class="dashboard-header">
      <div class="title-group">
        <h2>智能编排工作流控制台</h2>
        <span class="session-badge">Session: 2026_PROD_TEST</span>
      </div>
      <div class="action-group">
        <button 
          :disabled="pipelineRunning" 
          @click="startOrchestrator" 
          class="btn btn-primary"
        >
          {{ pipelineRunning ? '智能体工作流执行中...' : '启动流式编排' }}
        </button>
      </div>
    </header>

    <!-- 工作流主画布 -->
    <main class="dashboard-content">
      <!-- 左翼：思维链实时输出（传入响应式日志组） -->
      <div class="panel-wrapper">
        <CotConsole :logs="cotLogs" :isRunning="pipelineRunning" />
      </div>

      <!-- 右翼：资产聚合与安全熔断拦截面板 -->
      <div class="panel-wrapper right-workspace">
        <AssetViewer 
          :sqlCode="generatedSql" 
          :marketingText="generatedMarketing" 
        />

        <!-- 人工介入拦截面板 (HITL Brake) -->
        <div v-if="hitlSuspended" class="hitl-brake-panel">
          <div class="hitl-alert">
            <span class="alert-icon">⚠️</span>
            <div class="alert-text">
              <h4>安全防护栏触发：检测到敏感/大规模数据改动</h4>
              <p>当前智能体行为预计影响 <strong class="highlight">{{ targetRows }}</strong> 行生产数据。工作流已安全阻断挂起，请核验。</p>
            </div>
          </div>
          <div class="hitl-actions">
            <button @click="resolveHitl(true)" class="btn btn-success">核验批准，下发下游</button>
            <button @click="resolveHitl(false)" class="btn btn-danger">强行驳回，终止流程</button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue';
import CotConsole from './CotConsole.vue';
import AssetViewer from './AssetViewer.vue';

// --- 全局总线状态管理 ---
const pipelineRunning = ref(false);
const cotLogs = ref([]);
const generatedSql = ref('');
const generatedMarketing = ref('');
const hitlSuspended = ref(false);
const targetRows = ref(0);

let eventSource = null;

// --- 执行总线主干逻辑 ---
const startOrchestrator = () => {
  // 1. 初始化清理，防止污染
  cotLogs.value = [];
  generatedSql.value = '';
  generatedMarketing.value = '';
  hitlSuspended.value = false;
  targetRows.value = 0;
  pipelineRunning.value = true;

  const sessionId = 'DEBUG_TEST';
  const promptText = encodeURIComponent('触发核心高价值客群清洗与营销任务');
  const url = `/api/agents/stream-orchestrator?session_id=${sessionId}&prompt=${promptText}`;
  eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleStreamChunk(data);
    } catch (err) {
      console.error('解析后端 SSE 流 JSON 失败:', err);
    }
  };

  eventSource.onerror = (err) => {
    console.error('SSE 链接断开或完成:', err);
    closeStream();
  };
};

// --- 🌟 智能体多路资产分流路由（精密解耦去重版） ---
const handleStreamChunk = (data) => {
  const isCotStream = data.event === 'cot_stream' || data.type === 'cot';

  if (isCotStream) {
    const currentAgent = data.agent || data.agent_name || '未知智能体';
    let rawContent = data.content || '';

    // 【核心去重硬拦截】如果内容里包含了“智能体名字”或特定前缀，将其精准剔除
    if (rawContent.startsWith(currentAgent)) {
      rawContent = rawContent.replace(currentAgent, '').trim();
    }
    
    // 如果剔除名字后是空字符（比如单纯发了个名字过来），直接丢弃，不污染看板
    if (!rawContent) return;

    // 1. 寻找当前智能体在日志组中的最后一条记录，如果是同一个智能体在说话，直接“字串追加”
    const lastLog = cotLogs.value[cotLogs.value.length - 1];
    
    if (lastLog && lastLog.type === 'cot' && lastLog.agent === currentAgent) {
      // 完美合并：同一个智能体在连续吐字，直接 append
      lastLog.content += rawContent;
    } else {
      // 跃迁切换：新智能体开始说话，或者第一条消息，新开一行
      cotLogs.value.push({
        type: 'cot',
        agent: currentAgent,
        content: rawContent
      });
    }

    // 2. 根据 Agent 智能体类型标签实施垂直资产拦截
    if (currentAgent.includes('SQL') || currentAgent.includes('清洗') || currentAgent.includes('数据')) {
      generatedSql.value += rawContent;
    } else if (currentAgent.includes('营销') || currentAgent.includes('文案') || currentAgent.includes('策略')) {
      generatedMarketing.value += rawContent;
    } else {
      if (rawContent.includes('SELECT') || rawContent.includes('FROM') || rawContent.includes('WITH')) {
        generatedSql.value += rawContent;
      } else {
        generatedMarketing.value += rawContent;
      }
    }

  } else if (data.event === 'cot_start' || data.event === 'agent_transition') {
    cotLogs.value.push({
      event: data.event,
      content: `⚡ [智能体跃迁] 正在调度激活：${data.agent_name || 'System'}`
    });

  } else if (data.event === 'hitl_brake') {
    closeStream();
    cotLogs.value.push({
      event: 'hitl_brake',
      content: `🚨 [拦截告警] 触发人工核验：${data.content}`
    });
    
    targetRows.value = data.target_rows || 0;
    hitlSuspended.value = true;
    pipelineRunning.value = false;

  } else if (data.event === 'pipeline_finished') {
    cotLogs.value.push({
      event: 'pipeline_finished',
      content: '✅ [串联完成] 全链路流式多智能体工作流执行结束。'
    });
    closeStream();
  }
};

const resolveHitl = (approved) => {
  hitlSuspended.value = false;
  alert(approved ? '✅ 指令通过：资产已下发调度引擎执行。' : '❌ 指令驳回：回滚当前智能体所有缓存修改。');
};

const closeStream = () => {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  pipelineRunning.value = false;
};

onUnmounted(() => {
  closeStream();
});
</script>

<style scoped>
.agent-dashboard {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #0f141c;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  padding: 16px;
  box-sizing: border-box;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #1e293b;
  padding-bottom: 12px;
  margin-bottom: 16px;
}

.title-group h2 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
  color: #f8fafc;
}

.session-badge {
  font-size: 0.75rem;
  background-color: #1e293b;
  color: #38bdf8;
  padding: 2px 6px;
  border-radius: 4px;
  margin-top: 4px;
  display: inline-block;
}

.dashboard-content {
  display: flex;
  flex: 1;
  gap: 16px;
  min-height: 0; /* 阻止 Flexbox 子项撑爆高度导致的滚动失效 */
}

.panel-wrapper {
  flex: 1;
  min-width: 0;
  height: 100%;
}

.right-workspace {
  flex: 1.2;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* HITL 熔断器 */
.hitl-brake-panel {
  background-color: #2d1515;
  border: 1px solid #991b1b;
  border-radius: 8px;
  padding: 14px;
}

.hitl-alert {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.alert-icon { font-size: 1.6rem; }
.alert-text h4 { margin: 0 0 4px 0; color: #fca5a5; font-size: 0.95rem; }
.alert-text p { margin: 0; color: #f87171; font-size: 0.85rem; }
.highlight { font-size: 1rem; color: #ffffff; text-decoration: underline; }

.hitl-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

/* 按钮基础设计 */
.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  font-size: 0.88rem;
  cursor: pointer;
  transition: background 0.2s;
}
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary { background-color: #2563eb; color: #ffffff; }
.btn-primary:hover:not(:disabled) { background-color: #1d4ed8; }
.btn-success { background-color: #10b981; color: #ffffff; }
.btn-danger { background-color: #ef4444; color: #ffffff; }
</style>