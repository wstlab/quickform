# ECharts 图表示例（教学数据可视化常用）

CDN 引入（中国大陆可用）：
```html
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
```

---

## 1. 柱状图 — 成绩分布 / 各班对比

```javascript
const option = {
  title: { text: '班级答题得分对比', left: 'center', textStyle: { color: '#fff' } },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: ['一班', '二班', '三班', '四班'], axisLabel: { color: '#ccc' } },
  yAxis: { type: 'value', max: 100, axisLabel: { color: '#ccc' } },
  series: [{
    name: '平均分',
    type: 'bar',
    data: [85, 78, 92, 88],
    itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: '#83bff6' },
      { offset: 1, color: '#188df0' }
    ])}
  }]
};
```

---

## 2. 饼图 — 选项分布 / 答案占比

```javascript
const option = {
  title: { text: '答案选项分布', left: 'center', textStyle: { color: '#fff' } },
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: '5%', textStyle: { color: '#ccc' } },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],  // 环形图
    data: [
      { name: '选项A', value: 35 },
      { name: '选项B', value: 28 },
      { name: '选项C', value: 20 },
      { name: '选项D', value: 17 }
    ],
    emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } }
  }]
};
```

---

## 3. 折线图 — 实时答题趋势

```javascript
const option = {
  title: { text: '答题人数实时趋势', textStyle: { color: '#fff' } },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: timeLabels, boundaryGap: false },
  yAxis: { type: 'value' },
  series: [{
    type: 'line',
    data: countData,
    smooth: true,
    areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: 'rgba(58,77,233,0.8)' },
      { offset: 1, color: 'rgba(58,77,233,0.1)' }
    ])}
  }]
};
```

---

## 4. 仪表盘 — 正确率展示

```javascript
const option = {
  series: [{
    type: 'gauge',
    startAngle: 90, endAngle: -270,
    pointer: { show: false },
    progress: { show: true, overlap: false, roundCap: true },
    axisLine: { lineStyle: { width: 20 } },
    splitLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
    data: [{ value: 78, name: '正确率', title: { offsetCenter: ['0%', '30%'] } }],
    title: { fontSize: 18, color: '#fff' },
    detail: { fontSize: 30, color: '#fff', formatter: '{value}%' }
  }]
};
```

---

## 5. 排行榜（自定义 HTML，非 ECharts）

```html
<div class="leaderboard">
  <div class="rank-item" v-for="(item, index) in rankings">
    <span class="rank-num">{{ index + 1 }}</span>
    <span class="name">{{ item.name }}</span>
    <div class="score-bar" :style="{width: item.score + '%'}"></div>
    <span class="score">{{ item.score }}分</span>
  </div>
</div>
```

---

## 初始化与实时刷新模板

```javascript
// 初始化图表
const chart = echarts.init(document.getElementById('chart-container'));

async function loadAndRender() {
  const resp = await fetch('FETCH_URL');
  const rawData = await resp.json();
  
  // 处理数据...
  const processedData = processData(rawData);
  
  chart.setOption(buildOption(processedData));
}

// 首次加载
loadAndRender();

// 每15秒刷新
setInterval(loadAndRender, 15000);

// 窗口大小变化时自适应
window.addEventListener('resize', () => chart.resize());
```
