# QuickForm CLI（qf）参考文档

本文档是 `QFTools`（QuickForm助手）skill 的配套参考，介绍 quickform-cli（`qf` 命令行工具）的完整用法，以及 HTML 页面中数据接口（fetch）的说明。

> 本 skill 的**所有任务管理操作（创建任务、查看任务、提交测试数据、查询数据、绑定页面文件）一律使用 `qf` 命令**，不再使用裸 API 调用（curl POST）或 Python session 登录解析页面的方式。

---

## 1. 安装 CLI

```bash
# 安装官方命令行工具（需要 Python 3.9+）
pip install quickform-cli

# 查看版本，确认安装成功
qf --version
```

> 官方文档：https://quickform.cn/cli

---

## 2. 命令总览

| 命令 | 说明 | 是否需要登录 |
|------|------|:---:|
| `qf login` | 登录站点，凭据保存在本地 | — |
| `qf whoami` | 查看当前登录信息 | ✅ |
| `qf task add "名称" "描述"` | 创建数据任务，**直接返回 apiid** | ✅ |
| `qf task list` | 查看任务列表（名称与 API 地址） | ✅ |
| `qf task show <apiid>` | 查看任务详情；加 `--include-data` 一并返回全部提交数据 | ✅ |
| `qf task export <apiid> task.zip --include-data` | 导出任务为 ZIP（含任务描述、附件与提交数据） | ✅ |
| `qf task upload <apiid> file.html` | 为任务绑定页面文件，返回可访问 URL | ✅ |
| `qf submit <apiid> '{json}'` | 提交表单数据（公开接口） | ❌ |
| `qf data <apiid>` | 查看全部提交数据（公开接口） | ❌ |
| `qf brief <apiid>` | 查看最新 3 条提交数据（公开接口） | ❌ |
| `qf logout` | 清除本地登录凭据（不通知服务器） | — |

### ⚠️ `--base-url` 规则（最重要的坑）

`--base-url` 是**全局选项，必须放在子命令之前**：

```bash
# ✅ 正确
qf --base-url http://192.168.1.10:5001 task add "名称" "描述"

# ❌ 错误：放在子命令之后不生效
qf task add "名称" "描述" --base-url http://192.168.1.10:5001
```

- **在线版**（https://quickform.cn）：默认站点，**无需** `--base-url`。
- **校园版 / 教师版**（本地部署）：所有命令都需要 `--base-url <LOCAL_BASE_URL>` 指向本地服务。
- `qf submit` / `qf data` / `qf brief` 是公开数据接口，客户端不会读取已保存的站点地址，**每次都要带 `--base-url`**（在线版则不需要）。
- 登录成功后，`task` 系列命令与 `whoami` 会复用本地保存的凭据；`submit` / `data` / `brief` 不受影响。

---

## 3. 在线版用法

### 登录

```bash
qf login
# 按提示输入 quickform.cn 的账号和密码
```

### 完整示例

```bash
# 创建任务，输出中直接包含 apiid（随机字符串）
qf task add "三年级数学加减法练习" "课堂限时练习工具"

# 查看任务
qf task list
qf task show <apiid> --include-data

# 绑定教学页面文件，返回可访问 URL
qf task upload <apiid> ./数学练习_教学工具.html

# 提交测试数据（字段名与内容完全自定义，原样存储）
qf submit <apiid> '{"student_name":"张三","answer":"A","score":90}'

# 查询数据
qf data <apiid>
qf brief <apiid>

# 导出任务
qf task export <apiid> task.zip --include-data
```

### 创建任务的返回与常见错误

成功：

```json
{"success": true, "apiid": "AqfASqtCXPJ"}
```

失败：

```json
{"success": false, "message": "错误原因"}
```

常见错误处理：
- `已达任务数量上限（当前 3 个），无法创建新任务` → 请用户登录 quickform.cn 删除旧任务后重试
- 账号或密码错误 → 核对凭据后重新 `qf login`

---

## 4. 校园版 / 教师版用法

### 前置条件（两个，缺一不可）

1. **本地服务已启动**：教师版默认监听 `0.0.0.0:5001`（默认账号 `wst` / 密码 `quickform`）；校园版地址由学校 / 机构提供。
2. **CLI 功能已启用**：校园版 / 教师版以 QFLink 授权码为 CLI 开关。需先在「设置 → QFLink授权码」中填写 QFLink 授权码；未填写时**所有 `/cli/*` 请求返回 403**：

   ```
   CLI 功能未开启。请先在个人中心填写 QFLink 授权码以启用 CLI。
   ```

   遇到该报错时，指导用户到本地部署版页面的「设置 → QFLink授权码」完成填写，然后重新执行登录。

### 确定 LOCAL_BASE_URL

按以下优先级获取本地地址（详见 SKILL.md 第一阶段：步骤 1-1 ~ 1-3）：

1. 读取凭据缓存 `~/.trae-cn/quickform_credentials.json` 中的 `local.base_url`
2. 自动检测本机局域网 IP，拼接 `:5001` 后用 `curl -s -o /dev/null -w "%{http_code}"` 验证（200/302 即可用）
3. 询问用户手动输入（教师版提供实际地址；校园版地址由学校 / 机构提供）

> ⚠️ **不要使用 `127.0.0.1`**：仅本机可访问，学生用手机 / 其他电脑会打不开。请使用局域网 IP（如 `192.168.x.x:5001`）或校园内网域名。

### 登录与完整示例

```bash
# 登录本地站点（--base-url 必须放在子命令之前）
qf --base-url <LOCAL_BASE_URL> login
# 按提示输入账号密码（默认 wst / quickform；也可使用 用户名 + QFLink 授权码 认证）

# 创建任务（直接返回 apiid，无需再解析页面）
qf --base-url <LOCAL_BASE_URL> task add "三年级数学加减法练习" "课堂限时练习工具"

# 查询任务
qf --base-url <LOCAL_BASE_URL> task list
qf --base-url <LOCAL_BASE_URL> task show <apiid> --include-data

# 绑定教学页面文件
qf --base-url <LOCAL_BASE_URL> task upload <apiid> ./数学练习_教学工具.html

# 提交测试数据（公开接口，每次都要带 --base-url）
qf --base-url <LOCAL_BASE_URL> submit <apiid> '{"student_name":"张三","answer":"A","score":90}'

# 查询数据
qf --base-url <LOCAL_BASE_URL> data <apiid>
qf --base-url <LOCAL_BASE_URL> brief <apiid>
```

### 导出与导入任务

```bash
# 导出任务为 ZIP（含任务描述、附件与提交数据）
qf --base-url <LOCAL_BASE_URL> task export <apiid> task.zip --include-data
```

**导入**：CLI 暂无导入命令，需在本地部署版网页的「导入任务」页面（`/import_task`）上传 ZIP，或按任务 URL / 本地文件导入。

> 官方推荐：在**在线版**新建并调试数据任务，再导出 ZIP 导入到校园版 / 教师版。

### 常见报错

| 报错 | 原因与处理 |
|------|-----------|
| `403 CLI 功能未开启...` | 未填写 QFLink 授权码，或登录用的凭据不含有效授权码。到「设置 → QFLink授权码」填写后重新 `login` |
| 连接超时 / 拒绝连接 | `LOCAL_BASE_URL` 错误或服务未启动，先 `curl -I <LOCAL_BASE_URL>` 验证 |
| 账号或密码错误 | 核对凭据（默认 `wst` / `quickform`），或改用 用户名 + QFLink 授权码 |

> **旧版（1.5）的差异**：QuickForm 1.5 本地部署版没有 `/cli/*` 接口，只能 session 登录后用正则从 `/task/<数字id>` 页面解析 apiid。QuickForm 3.0 已内置完整 `/cli/*` 接口（`/cli/version`、`/cli/getuser`、`/cli/add`、`/cli/list`、`/cli/show`、`/cli/export_task`、`/cli/upload`），直接用 `qf` 命令即可，**apiid 由 `qf task add` 直接返回**，无需任何页面解析 hack。

---

## 5. 数据接口说明（供 HTML 页面 fetch 使用）

教学工具页面和数据大屏是**浏览器中的 HTML**，无法运行 `qf` 命令，需要直接调用 QuickForm 的公开数据接口。这些接口**无需登录**：

### 提交数据

```
POST <BASE>/api/<apiid>
Content-Type: application/json

{ "field1": "value1", "field2": 2, ... }
```

字段名称和内容完全自定义，QuickForm 原样存储。`<BASE>` 为 `https://quickform.cn`（在线版）或 `<LOCAL_BASE_URL>`（校园版 / 教师版）。

### 获取全部数据

```
GET <BASE>/api/<apiid>/all
```

QuickForm 3.0 返回标准 JSON（在线版与校园版 / 教师版一致）：

```json
{
  "note": "Total 3 submission(s).",
  "submissions": [
    { "field1": "value1", "field2": 2, "submitted_at": "2026-04-24 10:00:00" }
  ],
  "task_id": "<apiid>",
  "task_title": "任务名称",
  "total_submissions": 3
}
```

### 其他数据接口

| 接口 | 说明 |
|------|------|
| `GET <BASE>/api/<apiid>` | 最新 3 条提交数据 |
| `GET <BASE>/api/<apiid>/count` | 提交总数 |

### 页面端代码模板

```javascript
// 提交
async function submitData(formData) {
  const response = await fetch('SUBMIT_URL', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(formData)
  });
  return response.json();
}

// 大屏拉取
async function fetchData() {
  const response = await fetch('FETCH_URL');
  const data = await response.json();
  // data.submissions 为提交记录数组
  return data;
}
```

---

## 6. 仅老版本（QuickForm 1.5）需要的兼容方案

> **QuickForm 3.0 不需要本节内容**。仅当对接 QuickForm 1.5 老版本本地部署时，`/api/<apiid>/all` 返回的 `data` 字段是 **Python dict 字符串**（单引号），而非标准 JSON：

```json
{
  "submissions": [
    {
      "data": "{'student_name': '王小明', 'score': 3}",
      "id": 37,
      "submitted_at": "2026-04-25 07:48:06"
    }
  ]
}
```

大屏 HTML 中解析时需先转换：

```javascript
function parsePyDict(str) {
  const json = str
    .replace(/'/g, '"')
    .replace(/\bNone\b/g, 'null')
    .replace(/\bTrue\b/g, 'true')
    .replace(/\bFalse\b/g, 'false');
  return JSON.parse(json);
}

// 使用示例
const data = parsePyDict(submission.data);
```

QuickForm 3.0 已返回标准 JSON，直接 `response.json()` 即可。
