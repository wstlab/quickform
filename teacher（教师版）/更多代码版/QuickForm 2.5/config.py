import os
from dotenv import load_dotenv

load_dotenv()

# Flask 应用密钥，用于会话加密等安全功能
# 生产环境建议通过环境变量设置，避免使用默认值
SECRET_KEY = os.getenv('SECRET_KEY', 'dev_secret_key')

# SQLite 数据库连接地址
# 格式: sqlite:///相对路径 或 sqlite:////绝对路径
DATABASE_URL = 'sqlite:///data/quickform.db'

# 网页附件上传目录（任务编辑中上传的 HTML 等文件）
UPLOAD_FOLDER = 'static/assets'

# API 表单提交文件上传目录（通过 /api/<task_id> POST 上传的附件）
API_UPLOAD_FOLDER = 'static/uploads'

# Flask 请求体大小限制（16MB）
# 超过此限制会返回 413 Request Entity Too Large
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

# JSON 响应是否转义非 ASCII 字符
# False 表示中文直接输出，不做 Unicode 转义
JSON_AS_ASCII = False

# 任务附件允许上传的扩展名（白名单）
ALLOWED_EXTENSIONS = {'pdf', 'html', 'htm', 'jpg', 'zip'}

# 应用显示名称，用于页面标题、邮件模板等
APP_NAME = 'QuickForm教师版'

# 支持的语言列表
# key 为语言代码（Babel 格式），value 为显示名称
LANGUAGES = {
    'zh_CN': '简体中文',
    'zh_TW': '繁體中文',
    'en': 'English'
}

# API 文件上传默认大小限制（单位：MB）
# 用户可在「上传文件设置」中自定义，此为缺省值
DEFAULT_MAX_FILE_SIZE = 20

# API 文件上传默认允许扩展名
# 用户可在「上传文件设置」中自定义，此为缺省值
DEFAULT_ALLOWED_EXTENSIONS = 'jpg,jpeg,png,gif,webp,wav,mp3,webm,mp4,txt,pdf,doc,docx,html,htm,xls,xlsx,txt,zip'

# API 接口是否开启文件上传
# True 表示允许通过 API 上传文件，False 表示禁止
API_FILE_UPLOAD_ENABLED = True
