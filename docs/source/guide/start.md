# 入门：四步体验QuickForm

只要你用大模型（deepseek、豆包之类）制作过交互网页，就具备使用QuickForm的基础。QuickForm本身不具备生成交互网页的能力，但提供了数据接口，能够把网页数据汇总起来。

使用 QuickForm 收集交互网页数据非常简单，只需以下四步。

## 第一步：生成API地址

访问 QuickForm在线版（演示地址：[https://quickform.cn](https://quickform.cn)），注册账号后，在“数据任务”页面中点击“创建新任务”，系统将自动生成一个专属的API接口地址。该地址如同您的“数字收件箱”，所有学生提交的数据都会汇集于此。

![](../images/guide/start01-1.png)

![](../images/guide/start01-2.png)

## 第二步：生成交互网页

继续使用您熟悉的大模型（如 DeepSeek、GPT 等）生成交互网页，只需在提示词中加入一句：
“请以POST方式向（您的 QuickForm 数据接口地址）发送数据。”

![](../images/guide/start02-0.png)

大模型会自动在网页中嵌入数据提交功能。学生完成操作后，数据将通过接口自动存储至您的 QuickForm 账户，并于数据任务关联。

**注意：**你可以先让大模型制作普通的交互网页，再增加发送数据的指令，大模型基本上都能正确理解，并生成直接可用的网页代码。

![](../images/guide/start02-1.png)

![](../images/guide/start02-2.png)

所以，你之前做的不具备收集数据能力的网页，都可以用这种方法修改，增加功能。

## 第三步：收集与查看数据

你可以将生成的网页地址发给学生（豆包可以分享预览地址），也可以将网页上传到QuickForm的数据任务中，将得到一个访问地址。

![](../images/guide/start03-1.png)

学生使用交互网页并提交数据后，您可以在 QuickForm 任务界面实时查看所有提交记录。系统支持逐条查看详情，也支持批量导出为 Excel 表格，便于后续统计与存档。

![](../images/guide/start03-2.png)


## 第四步：生成智能报告

若数据量较大、手动分析困难，QuickForm 支持一键生成智能分析报告。系统可调用大模型对数据进行初步分析，生成包含提交人数、平均分、错误分布、高频问题等内容的可视化报告，帮助教师快速把握教学重点与难点。您也可导出数据，结合更精确的提示词进行深入分析。

注意：要一键生成智能分析报告，首先得有大模型的 APIKEY（API密钥）。具体请参考“大模型服务API密钥获取”。

![](../images/guide/start04.png)

你也可以生成实时的数据大屏，在教学过程中根据学生的学习情况调整教学进度，效果如下面视频所示。具体请参考“进阶：数据分析和大屏显示”。

<iframe src="//player.bilibili.com/player.html?isOutside=true&aid=116345144411966&bvid=BV1JpDNB6EM7&cid=37230871295&p=1" scrolling="no" border="0" frameborder="no" framespacing="0" allowfullscreen="true"></iframe>

## 总结：把QuickForm看成临时“数据储物柜”

需要说明的是，以上四个步骤并非固定。你可以先让大模型生成网页，再加入“QucikForm数据采集的提示词”，也可以直接一步到位，在提示词中把每个步骤都写清楚。

你可以把QuickForm后看成临时“数据储物柜”，存取“数据”的网络地址，那么就能做出各种精彩的互动网页来。任何需要回收数据的地方，都可以借助QuickForm的能力。总之，QuickForm以最低门槛和灵活操作，实现了大模型生成代码的数据回收。

最后，看一个简单的介绍视频吧，点击视频可以全屏观看。

<iframe src="//player.bilibili.com/player.html?isOutside=true&aid=116409233378089&bvid=BV1GXQJBgEwm&cid=37533321624&p=1" scrolling="no" border="0" frameborder="no" framespacing="0" allowfullscreen="true"></iframe>

