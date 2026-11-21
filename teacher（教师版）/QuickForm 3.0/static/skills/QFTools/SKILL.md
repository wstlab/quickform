---
name: QFTools
description: QuickForm助手 —— 让 AI 自动创建基于 QuickForm 的交互式教学工具，从需求收集、QuickForm 数据任务创建（通过 qf CLI 工具）、学生端网页开发、教师端实时分析网页（数据大屏）、附件上传，到任务合并打包与导出备份的全流程。当用户说"帮我做交互网页"、"帮我做交互课件"、"创建交互式教学页面"、"做一个课堂互动工具"、"用 QuickForm 做交互网页"、"制作学生互动表单页面"、"做数据采集教学工具"、"制作QF教学课件"等时，立即触发本 skill。只要涉及教学交互 + 数据收集 + 可视化任何组合，都应优先使用本 skill。
---

# QuickForm助手（QFTools）

## 概述

QuickForm助手（QFTools）帮助教师快速创建专业的交互式 HTML 教学工具，并自动对接 QuickForm 数据采集平台，最终生成实时分析数据的教师端网页。全程分为三个阶段：

- **第一阶段：第一次使用 —— 环境检测**（注册检查 → QFLink 授权码检查 → 版本选择）
- **第二阶段：开始工作**（生成数据任务 → 学生端网页 → 数据验证与教师端网页 → 上传附件）
- **第三阶段：后续工作（可选）**（合并 index.html 打包 zip → 导出/导入数据任务）

> **版本说明**：本 skill 是 [buBailai/quickform-teaching-tool](https://github.com/buBailai/quickform-teaching-tool) 的 **fork 版本**。与原始版本相比，核心改动：任务创建、测试数据提交、数据查询、附件上传等操作已全部从裸 API 调用（curl POST / Python session 登录解析页面）改为 quickform-cli（`qf` 命令行工具）。命令参考见 `references/quickform-api.md`。

---

## Skill 安装（以 WorkBuddy 为例）

本 skill 是一个标准 Agent Skill 目录（`SKILL.md` + `references/`），放入 AI 助手的全局 skills 目录即完成安装。

**WorkBuddy（全局安装）：**

```bash
# 将下载的 skill 安装包解压到 WorkBuddy 全局 skills 目录
unzip QFTools.zip -d ~/.trae-cn/skills/

# 确认安装
ls ~/.trae-cn/skills/QFTools/SKILL.md
```

安装后重新开启一个 WorkBuddy 对话，助手即可识别 `QFTools` skill；当用户提到"做教学工具""课堂互动工具"等需求时会自动触发。

> 其他支持 Agent Skills 规范的 AI 助手同理：把 `QFTools/` 目录放入对应助手的全局 skills 目录即可。

---

# 第一阶段：第一次使用 —— 环境检测

> 本阶段仅在**第一次使用**（或用户表示要换版本 / 换账号）时执行。若用户此前已完成配置，可直接跳到「第二阶段：开始工作」。

## 步骤 1-0：检查/安装 CLI 工具

先确认本机已安装 quickform-cli：

```bash
qf --version
```

若提示命令不存在，先安装（需要 Python 3.9+）：

```bash
pip install quickform-cli
```

## 步骤 1-1：检查是否已注册 quickform.cn

QuickForm 的在线版（https://quickform.cn）是账号体系与 QFLink 互联的中心，**三个版本都需要 quickform.cn 账号**。先向用户确认：

> "你是否已经注册了 quickform.cn 账号？"

- **已注册** → 询问账号密码并保存到凭据缓存 `~/.trae-cn/quickform_credentials.json`：
  ```json
  { "official": { "username": "账号", "password": "密码" } }
  ```
  写入命令（目录不存在时先 `mkdir -p ~/.trae-cn`）：
  ```bash
  echo '{"official":{"username":"xxx","password":"xxx"}}' > ~/.trae-cn/quickform_credentials.json
  ```
- **未注册** → 引导用户前往 https://quickform.cn 注册；并提醒：注册后建议完成**教师身份认证**（QFLink 互联功能仅已认证教师可用），完成后再继续。

## 步骤 1-2：检查是否已申请 QFLink 授权码

**QFLink 授权码的作用**：让本地部署版（校园版 / 教师版）通过 CLI 与在线版互通；本地部署版的 CLI 功能**以 QFLink 授权码为开关**，未填写时所有 `/cli/*` 请求返回 403。

向用户确认：

> "你是否已经申请过 QFLink 授权码？"

- **仅使用在线版** → 可跳过本步骤（在线版无需 QFLink 授权码）。
- **使用校园版 / 教师版** → 必须申请。指导用户操作：
  1. 登录本地部署版系统，点击右上角用户菜单 →「设置」
  2. 切换到「QFLink授权码」标签页
  3. 填写用途（例如：教师版 QFLink），点击「生成 QFLink 授权码」
  4. 把生成的授权码填入本地部署版 QFLink 配置并保存
- **未认证教师** → 若请求在线服务器返回 `403 certification_required`，说明账号未完成教师身份认证，需先在 quickform.cn 完成认证。

> 授权码可随时在「设置 → QFLink授权码」中停用，停用后旧码立即失效。

## 步骤 1-3：检查选择什么版本

向用户提问：

> "请问你要使用哪个版本的 QuickForm？
> - **A. 在线版**（https://quickform.cn，直接使用，无需本地服务）
> - **B. 校园版**（学校/机构统一部署的本地服务）
> - **C. 教师版**（本机部署的本地服务，默认端口 5001）"

### A. 在线版处理

- 无需 `--base-url`（使用默认站点）。
- 执行 CLI 登录：
  ```bash
  qf login
  ```
  按提示输入 quickform.cn 账号密码。

### B. 校园版处理

- 向用户询问学校/机构提供的访问地址（如 `http://10.0.0.5:5001` 或校园内网域名），并验证可访问：
  ```bash
  curl -s -o /dev/null -w "%{http_code}" <校园版地址>/
  ```
  返回 200 或 302 即可用。
- 确认 QFLink 授权码已填写（见步骤 1-2）。
- 登录时必须带 `--base-url`，且它是全局选项，**必须放在子命令之前**：
  ```bash
  qf --base-url <校园版地址> login
  ```
  按提示输入账号密码。

### C. 教师版处理（默认检查本机 5001）

1. **默认账号**：`wst`，**默认密码**：`quickform`。

2. **优先检查本地 5001 端口**（按以下优先级）：

   **第一步：检查是否已有保存的地址**
   ```bash
   cat ~/.trae-cn/quickform_credentials.json 2>/dev/null
   ```
   若 JSON 中已有 `local.base_url`，直接使用，告知用户"已使用上次保存的地址：xxx"，跳过后续检测。

   **第二步：自动检测本机局域网 IP + 5001 端口**
   ```python
   import socket
   s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
   s.connect(("8.8.8.8", 80))
   local_ip = s.getsockname()[0]
   s.close()
   print(local_ip)
   ```
   拼接为 `http://<local_ip>:5001` 并验证：
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://<local_ip>:5001/
   ```
   - 返回 200 或 302：告知用户"自动检测到本地地址：http://<local_ip>:5001，正在使用"，并保存到凭据文件。
   - 连接失败：进入第三步。

   **第三步：检测不到服务，询问用户下一步**
   ```
   未在本机 5001 端口检测到 QuickForm 服务，请选择：
   1) 在本机安装 QuickForm（教师版）—— 按官方部署方式完成安装后继续
   2) 已安装但地址不同 —— 请提供实际访问地址
   ```
   - 用户选择**安装** → 按官方提供的部署方式（官网 quickform.cn / 虚谷计划 https://www.vvplan.cn/）完成本地部署，安装完成后重新检测 5001。
   - 用户选择**提供地址** → 获取用户输入后再次验证，通过后保存。

   > ⚠️ **重要提醒**：最终地址**不要使用 `127.0.0.1`**。`127.0.0.1` 只在本机可访问，学生用手机或其他电脑打开时会失败。请使用本机**局域网 IP**（如 `192.168.x.x:5001`）或校园内网域名。

   **保存地址到凭据文件：**
   ```bash
   python3 -c "
   import json, os
   path = os.path.expanduser('~/.trae-cn/quickform_credentials.json')
   try:
       d = json.load(open(path))
   except:
       d = {}
   d.setdefault('local', {})['base_url'] = 'http://最终确认的地址'
   json.dump(d, open(path, 'w'), ensure_ascii=False)
   print('地址已保存')
   "
   ```

3. **确认 CLI 已启用**：教师版的 CLI 功能以 QFLink 授权码为开关（见步骤 1-2）。若用户未填写，先指导其在「设置 → QFLink授权码」完成填写再继续。

4. **CLI 登录**（教师版必须带 `--base-url`，且放在子命令之前）：
   ```bash
   qf --base-url <LOCAL_BASE_URL> login
   ```
   按提示输入账号密码（默认 `wst` / `quickform`）。

后续所有本地地址均使用变量 `LOCAL_BASE_URL`（校园版地址或教师版地址），不得硬编码 IP。

---

# 第二阶段：开始工作

## 步骤 2-1：分析任务，在 QuickForm 上生成数据任务

### ① 了解教学工具设计风格

向用户提问（提供选项引导，允许用户自由描述）：

> "请选择教学工具的设计风格（可多选或自行描述）：
> 1. 🎨 **简洁现代风** — 卡片布局、清爽配色，适合大多数场景
> 2. 🌈 **渐变炫彩风** — 鲜艳渐变、动感效果，适合活跃课堂
> 3. 🌙 **深色暗黑风** — 深色背景、荧光色彩，适合科技感课程
> 4. 🎠 **儿童友好风** — 圆润可爱、明亮卡通，适合小学低年级
> 5. 📊 **学术严肃风** — 专业整洁、数据导向，适合高中或大学
> 6. 🖌️ **自定义** — 请描述你想要的风格"

同时询问：适用年龄/年级、学科。

### ② 收集教学工具具体需求

必须涵盖三个维度：

**交互方式需求**
- 核心功能（投票/问卷/测验/实验记录/作品上传/讨论/游戏化练习等）
- 学生如何交互（点击选项/填写文本/拖拽/绘图/计时答题等）
- 是否需要即时反馈（答题后立即显示对错/解析）

如果用户描述模糊，追问：
> "你希望学生在这个页面上做什么操作？完成后会看到什么？"

**数据提交字段**（每个字段需明确 英文 key / 中文含义 / 类型）
```
student_name: 学生姓名（文字）
class: 班级（文字）
answer: 答案选项（A/B/C/D）
score: 得分（数字）
duration: 用时秒数（数字）
```

**教师端可视化需求**
- 希望看到哪些图表（柱状图/饼图/折线图/词云/排行榜等）
- 数据统计维度（按班级对比/答题分布/正确率/平均分/时间趋势等）
- 教师端整体风格、实时刷新间隔（默认 5 秒，可修改）

如果信息不足，追问：
> "在课堂上你想向全班展示什么数据？希望学生们看到自己在全班的哪个位置？"

### ③ 需求确认摘要

整理后展示给用户确认：

```
📋 需求确认摘要

【基本信息】
- QuickForm 版本：在线版 / 校园版 / 教师版
- 设计风格：xxx
- 适用年级：xxx  学科：xxx

【学生端交互】
- 功能类型：xxx
- 交互方式：xxx
- 即时反馈：是/否

【数据采集字段】
- field1: 含义 (类型)
- field2: 含义 (类型)
...

【教师端可视化】
- 图表类型：xxx
- 统计维度：xxx
- 实时刷新间隔：5 秒（默认）
```

等用户确认后再创建任务。

### ④ 用 qf CLI 创建数据任务

任务命名以教学工具主题命名（如"三年级数学加减法练习"）。

在线版：
```bash
qf task add "<任务名称>" "<工具简介>"
```

校园版 / 教师版：
```bash
qf --base-url <LOCAL_BASE_URL> task add "<任务名称>" "<工具简介>"
```

`qf task add` **直接返回任务的 API ID（apiid）**（随机字符串，如 `AqfASqtCXPJ`），从输出中提取即可，无需解析网页。

**创建失败处理：**
- 在线版提示"已达任务数量上限"：登录 quickform.cn 删除旧任务后重试
- 本地部署版返回 403 / "CLI 功能未开启"：先在「设置 → QFLink授权码」填写授权码，再重新 `qf --base-url <LOCAL_BASE_URL> login`
- 账号或密码错误：核对凭据后重新登录

### ⑤ 记录接口信息

创建成功后记录（`<BASE>` 为 `https://quickform.cn`、校园版地址或 `<LOCAL_BASE_URL>`）：
- `SUBMIT_URL`：数据提交接口 = `<BASE>/api/<apiid>`
- `FETCH_URL`：数据获取接口 = `<BASE>/api/<apiid>/all`
- `WS_URL`：实时推送订阅通道 = `<BASE>/ws/<apiid>`（`http://` → `ws://`，`https://` → `wss://`；本地部署版可用，在线版可能未开通）
- `TASK_NAME`：任务名称

> 以上两个数据接口是**公开接口**，供 HTML 页面在浏览器中直接 fetch；任务管理（创建/查看/导出）一律走 `qf` CLI。

---

## 步骤 2-2：生成学生端网页（数据发送到 API 地址）

基于需求生成一个完整的单文件 HTML **学生端网页**。

**技术规范：**
- 单一 HTML 文件，所有 CSS 和 JS 内联
- 使用中国大陆可顺利访问的 CDN
- 数据提交地址使用 `SUBMIT_URL`
- 提交成功后给学生清晰反馈（成功提示/得分/解析）
- 手机与电脑都能正常显示（响应式）

**推荐 CDN（中国大陆可访问）：**
```html
<!-- Tailwind CSS -->
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>

<!-- ECharts 图表（教师端用）-->
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>

<!-- Font Awesome 图标 -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6/css/all.min.css">

<!-- Alpine.js 轻量交互 -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
```

**数据提交代码模板：**
```javascript
async function submitData(formData) {
  try {
    const response = await fetch('SUBMIT_URL', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
    return await response.json();
  } catch (error) {
    console.error('提交失败:', error);
    return null;
  }
}
```

**质量要求：**
- 主题鲜明，符合选定设计风格
- 字体大小适合目标年龄段
- 交互元素有清晰视觉反馈（hover/点击动画）
- 提交按钮显眼、流程简洁
- 含标题与简短使用说明
- 所有表单字段与步骤 2-1 定义的字段完全对应

**文件保存**：`<任务名称_学生端>.html`

---

## 步骤 2-3：数据验证，生成教师端网页（实时分析）

### ① 提交测试数据做验证

按学生端字段结构生成 3 条真实感强的测试数据，用 `qf submit` 逐条提交。

**测试数据原则**：有差异（不能三条一样）、符合真实场景（真实姓名、合理分布）、覆盖不同情况（对的/错的、不同班级）。

在线版：
```bash
qf submit <apiid> '{"field1":"value1","field2":"value2"}'
```

校园版 / 教师版（`qf submit` 是公开数据接口，客户端不读取已保存的站点地址，**每次都要带 `--base-url`**）：
```bash
qf --base-url <LOCAL_BASE_URL> submit <apiid> '{"field1":"value1","field2":"value2"}'
```

提交 3 条后用 `qf data <apiid>`（本地部署版同样带 `--base-url`）确认数据已入库，向用户报告："✅ 已成功提交 3 条测试数据"。

### ② 获取真实数据结构

```bash
# 在线版
qf data <apiid>
# 校园版 / 教师版
qf --base-url <LOCAL_BASE_URL> data <apiid>
```

返回标准 JSON：
```json
{
  "note": "Total 3 submission(s).",
  "submissions": [ { "field1": "value1", "submitted_at": "2026-04-24 10:00:00" } ],
  "task_id": "<apiid>",
  "task_title": "任务名称",
  "total_submissions": 3
}
```

> QuickForm 3.0 校园版 / 教师版与在线版一样返回标准 JSON，无需 Python dict 字符串转换。（仅对接 QuickForm 1.5 老版本时才需 `parsePyDict`，见 `references/quickform-api.md`。）

### ③ 开发教师端网页（实时分析大屏）

综合真实数据结构、步骤 2-1 的可视化需求、学生端的主题风格开发。

**技术规范：**
- 单一 HTML 文件，代码内联
- 使用 ECharts 渲染图表
- 启动时自动从 `FETCH_URL` 拉取全量数据并渲染
- **实时更新：优先使用 WebSocket 推送**（本地部署版支持 `ws://<BASE>/ws/<apiid>` 订阅通道，每条新提交实时推送，无需轮询）；**若 5 秒内 WebSocket 连不上（如在线版未开通 WS），自动降级为每 5 秒轮询** `FETCH_URL`
- 布局适合投影展示（16:9 友好、字体偏大）

**必须包含：**
- 顶部：标题 + 核心指标总览（参与人数、平均分等）
- 主体：用户要求的图表（ECharts）
- 页脚小字：数据来源接口地址

**实时更新代码模板（原生 WebSocket，零依赖 + 自动降级轮询）：**
```javascript
// ===== 实时更新：WebSocket 优先，失败自动降级轮询 =====
const WS_URL = 'WS_URL';          // ws(s)://<BASE>/ws/<apiid>
const FALLBACK_INTERVAL = 5000;   // 降级轮询间隔（毫秒，可修改）
let ws = null;
let wsReady = false;
let pollTimer = null;

// 全量拉取（初始化 & 降级轮询共用）
async function fetchData() {
  const response = await fetch('FETCH_URL');
  const data = await response.json();
  render(data.submissions);   // data.submissions 为提交记录数组，按实际结构处理
}

// WebSocket 订阅：新提交实时推送
function connectWS() {
  try { ws = new WebSocket(WS_URL); } catch (e) { startPolling(); return; }

  const failTimer = setTimeout(() => {     // 5 秒连不上 → 降级轮询
    if (!wsReady) { try { ws.close(); } catch (e) {} startPolling(); }
  }, 5000);

  ws.onopen = () => { clearTimeout(failTimer); wsReady = true; stopPolling(); };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'connected') return;  // 订阅确认，忽略
    onData(msg);                           // msg 为一条新提交（含全部字段 + _submitted_at）
  };
  ws.onclose = () => {
    if (wsReady) setTimeout(connectWS, 3000);  // 正常连接过后断开 → 3 秒重连
    else startPolling();                        // 从未连上 → 降级轮询
  };
  ws.onerror = () => { try { ws.close(); } catch (e) {} };
}

// 降级轮询
function startPolling() { if (!pollTimer) { fetchData(); pollTimer = setInterval(fetchData, FALLBACK_INTERVAL); } }
function stopPolling()  { if (pollTimer)  { clearInterval(pollTimer); pollTimer = null; } }

fetchData();   // 初始全量渲染
connectWS();   // 尝试实时订阅
```

**说明：**
- `onData(newSubmission)`：把新提交追加到本地数组并增量重绘（比全量刷新更流畅）
- 连接成功会先收到一条 `{"type": "connected", ...}` 确认消息，直接忽略即可
- 在线版（quickform.cn）可能未开通 WS 通道——模板已内置自动降级，无需人工干预

**文件保存**：`<任务名称_教师端.html>`

---

## 步骤 2-4：上传附件，将两个网页绑定到数据任务

把**学生端网页**和**教师端网页**都上传到对应数据任务（`qf task upload` 会返回该文件的可访问 URL）：

```bash
# 学生端
qf task upload <apiid> <任务名称_学生端>.html

# 教师端
qf task upload <apiid> <任务名称_教师端>.html
```

校园版 / 教师版：
```bash
qf --base-url <LOCAL_BASE_URL> task upload <apiid> <任务名称_学生端>.html
qf --base-url <LOCAL_BASE_URL> task upload <apiid> <任务名称_教师端>.html
```

把返回的 URL 记录并告知用户：学生端 URL 发给学生使用，教师端 URL 供教师投屏查看。

---

# 第三阶段：后续工作（可选）

完成第二阶段后，主动询问用户是否需要以下两项收尾工作。

## 步骤 3-1：是否合并学生端与教师端网页，上传 zip

**先询问用户**："是否需要把学生端和教师端合并为一个入口页面（index.html），打包成 ZIP 上传？"

若需要：

1. 创建打包目录，把两个页面放入并规范命名：
   ```bash
   mkdir -p <任务名称>_package
   cp <任务名称_学生端>.html <任务名称>_package/student.html
   cp <任务名称_教师端>.html <任务名称>_package/teacher.html
   ```
2. 在目录中生成入口文件 `<任务名称>_package/index.html`，用链接或 `iframe` 把学生端与教师端连接为一体（例如两个标签/按钮切换 student.html 与 teacher.html）。
3. 打包 ZIP，**确保解压后的第一层目录下直接就是 index.html**：
   ```bash
   cd <任务名称>_package && zip -r ../<任务名称>.zip . -x "*.DS_Store"
   ```
   > 正确结构：`<任务名称>.zip` → `index.html`、`student.html`、`teacher.html`
   > 错误结构：`<任务名称>.zip` → `<任务名称>_package/` → `index.html`（多了一层目录，viewer 无法识别）
4. 在 QuickForm 的「编辑任务」页面把该 ZIP 作为附件上传（本地部署版 ZIP 附件通过 `/static/viewer.html?zip=<ZIP相对路径>` 预览）。
5. 告知用户上传结果与预览入口。

> 说明：ZIP 附件需在第一层目录下存在 `index.html` 入口文件；若缺少，viewer 页面会给出提示。

## 步骤 3-2：是否将数据任务导出为 zip，供下次导入

**先询问用户**："是否需要把当前数据任务导出为 ZIP 备份，方便以后导入复用？"

若需要：

1. 导出任务（含任务描述、附件与提交数据）：
   ```bash
   qf task export <apiid> <任务名称>.zip --include-data
   # 校园版 / 教师版：
   qf --base-url <LOCAL_BASE_URL> task export <apiid> <任务名称>.zip --include-data
   ```
2. 告知用户导出文件位置。
3. **下次导入**：在本地部署版（校园版 / 教师版）的「导入任务」页面（`/import_task`）上传该 ZIP 即可恢复任务；也可通过任务 URL 或本地文件导入。
   > 官方推荐做法：在**在线版**新建并调试数据任务，再导出 ZIP 导入到校园版或教师版使用。

---

## 完成报告

全部完成后输出简要报告：

```
🎉 QuickForm 教学工具开发完成！

📁 生成文件
  - 学生端网页：<文件名>.html
  - 教师端网页：<文件名>.html
  - （可选）打包入口：<任务名称>.zip

🔗 接口信息
  - 任务 API ID：apiid
  - 数据提交：SUBMIT_URL
  - 数据获取：FETCH_URL
  - 实时推送订阅（本地部署版）：WS_URL
  - 学生端分享地址：（步骤 2-4 上传后返回的 URL）
  - 教师端分享地址：（步骤 2-4 上传后返回的 URL）

📊 测试数据
  - 已通过 qf submit 提交 3 条测试数据，可在教师端页面查看效果

💡 使用提示
  1. 把学生端地址分享给学生（或使用合并后的 index.html 入口）
  2. 学生提交后，打开教师端页面实时查看（默认每 5 秒刷新）
  3. 如需修改样式、字段或刷新间隔，直接编辑 HTML 文件
  4. 后续可用 `qf data <apiid>` 随时在命令行查看全部数据
```

---

## 参考资料

- QuickForm CLI（qf）参考文档：见 `references/quickform-api.md`
- 可视化图表示例：见 `references/echarts-examples.md`
- 中国可用 CDN 列表：见 `references/china-cdn.md`
