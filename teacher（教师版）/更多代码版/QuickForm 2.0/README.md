# QuickForm教师版2.0（纯代码版）

## 软件说明

QuickForm是温州科技高级中学AI科创中心联合温州大学开发的智能表单管理服务，是一个为AI赋能教学而生的开源教学辅助系统。教师借助AI大模型生成交互网页后，可以借助QuickForm提供的API接口回收数据。教师通过对学习数据的智能分析，走向基于数据的精准教学。

本软件为QuickForm教师版，版本号2.0，仅提供纯代码，需要用户自己搭建Python环境。

## 使用方法

下载压缩包后，解压，安装 Python 环境，推荐3.11版本。

用Python直接运行"app.py"。

## 内置管理信息

用户名：wst

密码：quickform

## 最新升级说明

版本2.0新增功能：
- 新增“QF数据互联”功能，支持从quickform.cn在线版导入任务（ZIP文件导入和API导入），导入任务时自动下载并替换HTML附件中的API地址
- AI配置中，支持Ollama本地AI模型连接
- 用户信息修改：支持修改用户名和密码
- 数据任务支持无限附件上传，自动生成二维码，扫描即可访问

## 系统要求

任何能运行Python的系统都可以，包括Windows、MacOS、Linux等。

## 系统演示

https://quickform.cn

## 开源地址

https://gitee.com/wstlab/quickform
