---
name: quickform-teaching-tool
description: 创建基于 QuickForm 的交互式教学工具，自动完成从需求收集、QuickForm 任务创建（通过 qf CLI 工具）、HTML 教学页面开发、测试数据提交、到数据可视化分析大屏的全流程开发。当用户说"帮我做教学工具"、"创建交互式教学页面"、"做一个课堂互动工具"、"用 QuickForm 做教学"、"制作学生互动表单页面"、"做数据采集教学工具"、"制作可视化教学页面"等时，立即触发本 skill。只要涉及教学交互 + 数据收集 + 可视化任何组合，都应优先使用本 skill。
---

# QuickForm 交互式教学工具创建 Skill（CLI 版）

## 概述

本 skill 帮助教师快速创建专业的交互式 HTML 教学工具，并自动对接 QuickForm 数据采集平台，最终生成数据分析可视化大屏。全程分 8 步完成。

> **版本说明**：本 skill 是 [buBailai/quickform-teaching-tool](https://github.com/buBailai/quickform-teaching-tool) 的 **fork 版本**。与原始版本相比，核心改动：任务创建、测试数据提交、数据查询等操作已全部从裸 API 调用（curl POST / Python session 登录解析页面）改为 quickform-cli（`qf` 命令行工具），官网版与本地版统一使用 CLI。命令参考见 `references/quickform-api.md`。

---

## Skill 安装（以 WorkBuddy 为例）

本 skill 是一个标准 Agent Skill 目录（`SKILL.md` + `references/`），放入 AI 助手的全局 skills 目录即完成安装。

**WorkBuddy（全局安装）：**

```bash
# 将下载的 skill 安装包解压到 WorkBuddy 全局 skills 目录
unzip quickform-teaching-tool.zip -d ~/.trae-cn/skills/

# 确认安装
ls ~/.trae-cn/skills/quickform-teaching-tool/SKILL.md
```

安装后重新开启一个 WorkBuddy 对话，助手即可识别 `quickform-teaching-tool` skill；当用户提到"做教学工具""课堂互动工具"等需求时会自动触发。

> 其他支持 Agent Skills 规范的 AI 助手同理：把 `quickform-teaching-tool/` 目录放入对应助手的全局 skills 目录即可。

---

## 步骤 1：确认 QuickForm 版本与账号，准备 CLI 环境

### 1.0 检查/安装 CLI 工具

先确认本机已安装 quickform-cli：

```bash
qf --version
```

若提示命令不存在，先安装（需要 Python 3.9+）：

```bash
pip install quickform-cli
```

### 询问用户使用哪个版本

向用户提问：
> "请问你要使用哪个版本的 QuickForm？
> - **A. 官网版**（https://quickform.cn）
> - **B. 本地版**（局域网部署版）"

### 官网版处理

1. 检查凭据缓存文件 `~/.trae-cn/quickform_credentials.json` 是否存在：
   ```bash
   cat ~/.trae-cn/quickform_credentials.json 2>/dev/null
   ```
2. 若文件存在且包含 `official.username` 和 `official.password`，直接读取使用，**无需再次询问**，告知用户"已使用上次保存的账号：xxx"
3. 若不存在，询问用户官网账号和密码，获取后保存到缓存文件：
   ```json
   {
     "official": {
       "username": "用户提供的账号",
       "password": "用户提供的密码"
     }
   }
   ```
   用 bash 写入（目录不存在时先 `mkdir -p ~/.trae-cn`）：`echo '{"official":{"username":"xxx","password":"xxx"}}' > ~/.trae-cn/quickform_credentials.json`

4. **CLI 登录**（官网版使用默认站点，无需 `--base-url`）：
   ```bash
   qf login
   ```
   按提示输入官网账号密码。登录成功后，`task` 系列命令与 `whoami` 会复用本地保存的凭据。

### 本地版处理

1. 默认账号：`wst`，默认密码：`quickform`（本地部署的出厂默认值，保持不变）

2. **自动获取本地地址**（按以下优先级依次尝试）：

   **第一步：检查是否已有保存的地址**
   ```bash
   cat ~/.trae-cn/quickform_credentials.json 2>/dev/null
   ```
   若 JSON 中已有 `local.base_url` 字段，直接使用，告知用户"已使用上次保存的本地地址：xxx"，跳过后续检测。

   **第二步：自动检测本机 IP + 5001 端口**
   若无保存地址，先用 Python 获取本机局域网 IP：
   ```python
   import socket
   s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
   s.connect(("8.8.8.8", 80))
   local_ip = s.getsockname()[0]
   s.close()
   print(local_ip)
   ```
   拼接为 `http://<local_ip>:5001`，然后验证是否可用：
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://<local_ip>:5001/
   ```
   - 若返回 200 或 302：告知用户"自动检测到本地地址：http://<local_ip>:5001，正在使用"，并保存到凭据文件
   - 若连接失败：进入第三步

   **第三步：自动检测失败，询问用户手动输入**
   ```
   自动检测地址 http://<local_ip>:5001 无法访问，请手动输入本地 QuickForm 的访问地址
   （例如：http://192.168.1.100:5001）：
   ```
   获取用户输入后再次验证，验证通过后保存。

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

3. 询问用户："本地 QuickForm 服务是否已启动？如未启动请先启动服务。"

4. **确认 CLI 已启用（本地版特有）**：本地版的 CLI 功能以 QFLink 授权码为开关。请用户确认已在「个人中心 → QFLink」中填写 QFLink 授权码；未填写时所有 CLI 命令都会被拒绝（返回"CLI 功能未开启"）。若用户表示没填过，指导其打开本地版页面的个人中心完成填写后再继续。

5. **CLI 登录**（本地版必须带 `--base-url`，且它是全局选项，**必须放在子命令之前**）：
   ```bash
   qf --base-url <LOCAL_BASE_URL> login
   ```
   按提示输入账号密码（默认 `wst` / `quickform`）。

后续步骤中所有本地地址均使用变量 `LOCAL_BASE_URL`（从上述流程中获取），不得硬编码 IP。

---

## 步骤 2：了解教学工具设计风格

向用户提问（提供选项引导，允许用户自由描述）：

> "请选择教学工具的设计风格（可多选或自行描述）：
> 1. 🎨 **简洁现代风** — 卡片布局、清爽配色，适合大多数场景
> 2. 🌈 **渐变炫彩风** — 鲜艳渐变、动感效果，适合活跃课堂
> 3. 🌙 **深色暗黑风** — 深色背景、荧光色彩，适合科技感课程
> 4. 🎠 **儿童友好风** — 圆润可爱、明亮卡通，适合小学低年级
> 5. 📊 **学术严肃风** — 专业整洁、数据导向，适合高中或大学
> 6. 🖌️ **自定义** — 请描述你想要的风格"

同时询问：
- 适用年龄/年级（如：小学3年级、初中二年级、高中生、大学生）
- 学科（如：语文、数学、英语、科学、信息技术、历史等）

---

## 步骤 3：收集教学工具具体需求

这一步需要收集足够详细的信息才能开始开发。必须涵盖以下三个维度：

### 3.1 交互方式需求
必须明确：
- 教学工具的核心功能是什么（投票/问卷/测验/实验记录/作品上传/讨论/游戏化练习等）
- 学生如何与工具交互（点击选项/填写文本/拖拽/绘图/计时答题等）
- 是否需要即时反馈（答题后立即显示对错/解析）

如果用户描述模糊，主动追问：
> "你希望学生在这个页面上做什么操作？完成后会看到什么？"

### 3.2 数据提交字段

必须明确每个要收集的字段：
- 字段名称（英文 key，用于数据接口）
- 字段含义（中文说明）
- 字段类型（文字/数字/选项/时间等）

如果用户没提到字段，引导他们思考：
> "你希望收集学生的哪些信息？比如：学生姓名、班级、答题选项、得分、用时等，请逐一说明。"

示例字段格式（供参考，实际以用户需求为准）：
```
student_name: 学生姓名（文字）
class: 班级（文字）
answer: 答案选项（A/B/C/D）
score: 得分（数字）
duration: 用时秒数（数字）
```

### 3.3 数据分析/可视化大屏需求

必须明确：
- 希望看到哪些图表（柱状图/饼图/折线图/词云/排行榜等）
- 数据统计维度（按班级对比/答题分布/正确率/平均分/时间趋势等）
- 大屏整体风格（与教学工具一致/独立风格/投影展示风格）
- 是否需要实时刷新

如果信息不足，追问：
> "在课堂上你想向全班展示什么数据？希望学生们看到自己在全班的哪个位置？"

### 信息确认

收集完以上三个维度后，整理一份需求摘要展示给用户确认，格式如下：

```
📋 需求确认摘要

【基本信息】
- QuickForm版本：官网版/本地版
- 设计风格：xxx
- 适用年级：xxx  学科：xxx

【教学工具交互】
- 功能类型：xxx
- 交互方式：xxx
- 即时反馈：是/否

【数据采集字段】
- field1: 含义 (类型)
- field2: 含义 (类型)
...

【可视化大屏需求】
- 图表类型：xxx
- 统计维度：xxx
- 是否实时刷新：是/否
```

等用户确认后再进入步骤 4。

---

## 步骤 4：通过 qf CLI 创建 QuickForm 任务

根据步骤 1 完成的登录，使用 `qf task add` 命令创建任务（**不再使用 curl 或 session 登录方式**）。

**任务命名规则**：以教学工具的主题命名，简洁明了（如"三年级数学加减法练习"、"高中化学元素周期表测验"）

### 官网版创建

```bash
qf task add "<任务名称>" "<工具简介>"
```

### 本地版创建

```bash
qf --base-url <LOCAL_BASE_URL> task add "<任务名称>" "<工具简介>"
```

`qf task add` 会**直接返回任务的 API ID（apiid）**（随机字符串，如 `AqfASqtCXPJ`），无需再登录网页解析任务详情页面。从命令输出中提取 apiid。

**创建失败处理：**
- 官网版提示"已达任务数量上限"：请用户登录 quickform.cn 删除旧任务后重试
- 本地版返回 403 / "CLI 功能未开启"：请用户先在「个人中心 → QFLink」填写 QFLink 授权码，然后重新执行 `qf --base-url <LOCAL_BASE_URL> login` 再创建
- 提示账号或密码错误：核对凭据后重新登录

### 记录接口信息

创建成功后，将以下信息记录下来供后续步骤使用（`<BASE>` 为 `https://quickform.cn` 或 `<LOCAL_BASE_URL>`）：
- `SUBMIT_URL`：数据提交接口地址 = `<BASE>/api/<apiid>`
- `FETCH_URL`：数据获取接口地址 = `<BASE>/api/<apiid>/all`
- `TASK_NAME`：任务名称

> 注意：以上两个数据接口是**公开接口**，供后续生成的 HTML 页面在浏览器中直接 fetch 调用；而任务管理（创建/查看/导出）一律走 `qf` CLI。

---

## 步骤 5：开发交互式 HTML 教学工具页面

基于所有收集的需求，生成一个完整的单文件 HTML 教学工具。

### 技术规范

**必须遵守的原则：**
- 单一 HTML 文件，所有 CSS 和 JS 内联
- 使用中国大陆可顺利访问的 CDN（见下方列表）
- 数据提交地址使用 `SUBMIT_URL`
- 提交成功后给学生清晰的反馈（成功提示/得分/解析）
- 页面必须在手机和电脑上都能正常显示（响应式）

**推荐 CDN（中国大陆可访问）：**
```html
<!-- Tailwind CSS -->
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>

<!-- ECharts 图表（可视化页面用）-->
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
    const result = await response.json();
    return result;
  } catch (error) {
    console.error('提交失败:', error);
    return null;
  }
}
```

### 教学工具质量要求

- 页面主题鲜明，符合选定的设计风格
- 字体大小适合目标年龄段（儿童用更大字体）
- 交互元素有清晰的视觉反馈（hover 效果、点击动画）
- 提交按钮显眼，提交流程简洁（步骤少）
- 包含教学工具标题、简短使用说明
- 所有表单字段与步骤 3.2 定义的字段完全对应

### 文件保存

将生成的 HTML 保存到当前工作目录，命名规则：
`<任务名称_教学工具>.html`（中文可以用拼音缩写，空格用下划线）

### （推荐）用 CLI 将教学页面绑定到任务，获取分享地址

```bash
qf task upload <apiid> <教学工具文件路径>.html
# 本地版：
qf --base-url <LOCAL_BASE_URL> task upload <apiid> <教学工具文件路径>.html
```

命令返回该页面的可访问 URL，直接发给学生即可打开使用（免去手动托管网页）。

---

## 步骤 6：通过 qf CLI 自动提交 3 条测试数据

根据教学工具的字段结构，生成 3 条真实感强的测试数据，用 `qf submit` 逐条提交（**不再使用 curl**）。

**测试数据原则：**
- 数据要有差异性（不能三条一模一样）
- 数据要符合真实场景（真实的学生名字、合理的成绩分布）
- 覆盖不同情况（如：答对的、答错的、不同班级的）

**提交方式：**

官网版：
```bash
qf submit <apiid> '{"field1":"value1","field2":"value2"}'
```

本地版（`qf submit` 是公开数据接口，客户端不会读取已保存的站点地址，**每次都要带 `--base-url`**）：
```bash
qf --base-url <LOCAL_BASE_URL> submit <apiid> '{"field1":"value1","field2":"value2"}'
```

提交 3 条后，可用 `qf data <apiid>`（本地版同样带 `--base-url`）确认数据已入库。

完成后告知用户："✅ 已成功提交 3 条测试数据"

---

## 步骤 7：开发数据分析可视化大屏

### 7.1 获取测试数据结构

用 `qf data` 命令获取全部提交数据（**不再使用 curl**）：

官网版：
```bash
qf data <apiid>
```

本地版：
```bash
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

读取返回的完整 JSON 数据，理解数据结构（字段名、数据类型、嵌套关系），将完整数据结构记录下来作为开发参考。

> QuickForm 3.0 本地版与官网版一样返回标准 JSON，无需再做 Python dict 字符串转换。（仅当对接 QuickForm 1.5 老版本时，`data` 字段才是单引号 dict 字符串，需参考 `references/quickform-api.md` 中的 parsePyDict 兼容方案。）

### 7.2 开发可视化大屏 HTML

基于以下信息综合开发：
- 步骤 7.1 获取的真实数据结构和字段
- 步骤 3.3 用户提出的可视化需求
- 教学工具页面的主题和风格（保持一致性）

**技术规范：**
- 单一 HTML 文件，所有代码内联
- 使用 ECharts（`cdn.jsdelivr.net`）渲染图表
- 页面启动时自动从 `FETCH_URL` 获取数据并渲染
- 如需实时刷新，使用 `setInterval` 每 10-15 秒刷新一次
- 大屏布局适合投影展示（16:9 比例友好，字体偏大）

**大屏必须包含：**
- 页面顶部：工具标题 + 当前数据统计总览（参与人数、平均分等核心指标）
- 主体区域：用户需求的图表（使用 ECharts）
- 数据来源接口地址（页脚小字显示）

**数据获取代码模板：**
```javascript
async function fetchData() {
  const response = await fetch('FETCH_URL');
  const data = await response.json();
  // data.submissions 为提交记录数组，按步骤 7.1 实际结构处理
  return data;
}
```

### 文件保存

命名规则：`<任务名称_数据大屏>.html`

---

## 步骤 8：完成报告

开发完成后，向用户输出一份简要报告：

```
🎉 QuickForm 教学工具开发完成！

📁 生成文件
  - 教学工具页面：<文件名>.html
  - 数据分析大屏：<文件名>.html

🔗 接口信息
  - 任务 API ID：apiid
  - 数据提交：SUBMIT_URL
  - 数据获取：FETCH_URL
  - 教学页面分享地址：（若步骤 5 执行了 qf task upload 则附上返回的 URL）

📊 测试数据
  - 已通过 qf submit 提交 3 条测试数据，可在大屏页面查看效果

💡 使用提示
  1. 将教学工具页面分享给学生（分享地址或自行托管）
  2. 学生填写提交后，打开数据大屏实时查看结果
  3. 如需修改样式或字段，直接编辑 HTML 文件
  4. 后续可用 `qf data <apiid>` 随时在命令行查看全部数据
```

---

## 参考资料

- QuickForm CLI（qf）参考文档：见 `references/quickform-api.md`
- 可视化图表示例：见 `references/echarts-examples.md`
- 中国可用 CDN 列表：见 `references/china-cdn.md`
