# QuickForm教师版3.0（纯代码版）

## 软件说明

QuickForm是一个由温州科技高级中学和温州大学联合开发的开源数据服务项目，专门为大模型生成的交互网页而设计，嵌入专用地址后即可实现数据收集、分析与报告生成。QuickForm发布半年后拥有数万教师用户，称为教师创AI的最佳搭档之一。随着用户增多和需求提升，QuickForm逐步从交互网页辅助工具发展为一个通用的数据服务。

版本号：3.0.0

## 使用方法

本软件为QuickForm教师版，版本号3.0.0，仅提供源代码，需要用户自己搭建Python环境。

下载压缩包后，解压，推荐使用WorkBuddy、豆包工作等工具配置环境。参考提示词：为这个QuickForm教师版配置Python环境，并运行 "app.py" 。

第一次登录，可以用内置的管理账号（用户名：wst，密码：quickform）登录系统，也可以使用在线版的用户名和密码，记得及时修改密码。

**安全提示：**请勿在 QuickForm 中存储姓名、身份证号等敏感数据，详情查看“免责声明”。

## 最新升级说明

- 修复API输出数据格式，和quickform.cn在线版保持一致，数据任务导入即可使用，并实现同步导入数据；
- 支持数据任务的导出功能，包含数据并打包其他文件；
- 增加在线编辑网页功能，可智能替换API地址，自适应不同IP地址；
- 支持多网页上传功能（zip包），访问时自动解压并展示；
- 新增WebSocket实时推送，教师端网页可实时接收学生提交数据（详见下方"WebSocket实时推送"）；
- 所有API与WS接口响应均携带 `help` 字段，指向 `/tutorials` 教程页，方便AI智能体自助获取帮助；

## 系统要求

任何能运行Python的系统，包括Windows、MacOS、Linux等。

## WebSocket实时推送

QuickForm 3.0 内置WebSocket服务（基于flask-sock + eventlet），教师端网页无需轮询即可实时接收学生的每一条提交数据，适用于抢答、实时投票、课堂大屏等场景。

**注：**在线版不提供WebSocket服务，仅支持轮询方式获取数据。

### 连接方式

每个数据任务对应一个订阅地址（`apiid` 为任务的API ID）：

```
ws://<服务器地址>:5001/ws/<apiid>
```

例如本机部署时：`ws://192.168.31.8:5001/ws/uvauKltUpQK`（注意不要用127.0.0.1，其他设备无法访问）。

浏览器中原生 `new WebSocket()` 即可连接，无需任何第三方库。

### 消息协议

1. **连接确认**：连接成功后服务端立即推送一条 `type=connected` 的JSON消息（含任务名称、教程链接），前端可据此确认订阅成功，该消息无需展示：

```json
{
  "type": "connected",
  "task_id": "uvauKltUpQK",
  "task_title": "课堂投票",
  "help": "http://192.168.31.8:5001/tutorials",
  "note": "New submissions will be pushed in real time. ..."
}
```

2. **实时推送**：之后学生每提交一条数据，服务端实时推送一条JSON，包含学生提交的全部字段，并附加 `_submitted_at`（提交时间）、`_submission_id`（提交序号）、`_ip`（来源IP）：

```json
{
  "姓名": "张三",
  "选项": "A",
  "_submitted_at": "2026-11-20 11:30:00",
  "_submission_id": 42,
  "_ip": "192.168.31.20"
}
```

3. **心跳**：客户端可定时发送文本 `ping`，服务端回复 `pong`，用于保活检测。

### 前端代码示例（原生WebSocket + 自动降级轮询）

```javascript
const WS_URL = 'ws://192.168.31.8:5001/ws/uvauKltUpQK';   // 换成实际地址
const FETCH_URL = 'http://192.168.31.8:5001/api/uvauKltUpQK/all';

async function fetchData() {                                 // 降级方案：每5秒轮询
  const res = await fetch(FETCH_URL);
  const data = await res.json();
  render(data.submissions);
}

let ws = null, wsReady = false, pollTimer = null;
function connectWS() {
  try { ws = new WebSocket(WS_URL); } catch (e) { startPolling(); return; }
  const failTimer = setTimeout(() => {                       // 5秒连不上则降级
    if (!wsReady) { try { ws.close(); } catch (e) {} startPolling(); }
  }, 5000);
  ws.onopen = () => { clearTimeout(failTimer); wsReady = true; stopPolling(); };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'connected') return;                    // 忽略连接确认消息
    onData(msg);                                             // 处理每条实时提交
  };
  ws.onclose = () => {                                       // 断开后3秒重连
    if (wsReady) setTimeout(connectWS, 3000);
    else startPolling();
  };
  ws.onerror = () => { try { ws.close(); } catch (e) {} };
}
function startPolling() { if (!pollTimer) { fetchData(); pollTimer = setInterval(fetchData, 5000); } }
function stopPolling()  { if (pollTimer)  { clearInterval(pollTimer); pollTimer = null; } }

fetchData();
connectWS();
```

### 使用提示

- 详细的提示词写法（普通提交 / 多模态提交 / 实时交互提交）见系统内置教程页：`http://<服务器地址>:5001/tutorials`；
- 数据任务的"数据提交说明"卡片中提供了三种现成提示词，可直接复制给AI助手生成学生端和教师端网页；
- WebSocket地址规则：REST接口 `http(s)://` 对应 `ws(s)://`，路径由 `/api/<apiid>` 改为 `/ws/<apiid>`；
- REST接口始终可用（`GET /api/<apiid>/all` 一次获取全部数据），WebSocket仅用于实时推送，两者可并用。

## 系统演示

https://quickform.cn

## 开源地址

https://gitee.com/wstlab/quickform
