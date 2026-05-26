import os, json, re, uuid, random, string, io, base64, logging, threading, time
import requests, urllib.parse, pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, make_response, send_file, send_from_directory, session
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask_babel import Babel, gettext, ngettext, lazy_gettext, _
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # 输出到控制台
    ]
)

logger = logging.getLogger(__name__)


# 加载环境变量
load_dotenv()

import config as cfg

app = Flask(__name__)
app.config['SECRET_KEY'] = cfg.SECRET_KEY
app.config['UPLOAD_FOLDER'] = cfg.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = cfg.MAX_CONTENT_LENGTH
app.config['JSON_AS_ASCII'] = cfg.JSON_AS_ASCII

APP_NAME = cfg.APP_NAME

# 初始化Flask-Babel
babel = Babel()

def get_locale():
    lang = session.get('language')
    if lang in cfg.LANGUAGES:
        return lang
    return 'zh_CN'

babel.init_app(app, locale_selector=get_locale)

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in cfg.LANGUAGES:
        session['language'] = lang
    return redirect(request.referrer or '/')

# 初始化SQLAlchemy
engine = create_engine(cfg.DATABASE_URL, connect_args={'check_same_thread': False, 'timeout': 15})

# 启用 SQLite WAL 模式，提升并发读写性能
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 注册模板全局变量
@app.template_global()
def get_app_name():
    return APP_NAME

@app.template_global()
def get_current_language():
    return session.get('language', 'zh_CN')

@app.template_global()
def get_languages():
    return cfg.LANGUAGES

@app.template_filter('from_json')
def from_json_filter(s):
    try:
        return json.loads(s)
    except:
        return None

# 用于存储分析任务进度的字典（在生产环境中应使用Redis等）
analysis_progress = {}
analysis_results = {}
# 用于跟踪已成功生成报告的任务ID，避免重复生成
completed_reports = set()
# 线程锁，确保对共享数据的安全访问
progress_lock = threading.Lock()

# 工具函数
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in cfg.ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    try:
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            random_name = uuid.uuid4().hex[:10]
            unique_filename = f"{random_name}.{ext}" if ext else random_name
            os.makedirs(cfg.UPLOAD_FOLDER, exist_ok=True)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            filepath = filepath.replace('\\', '/')
            return unique_filename, filepath
    except Exception as e:
        logger.error(f"保存文件失败: {str(e)}")
    return None, None

def generate_custom_id():
    """
    生成11位自定义ID：9位数字和字母组合 + 2位大写字母
    例如：oU59mLzPJPU
    """
    chars = string.ascii_letters + string.digits
    prefix = ''.join(random.choices(chars, k=9))
    suffix = ''.join(random.choices(string.ascii_uppercase, k=2))
    return prefix + suffix

# 数据库模型
class User(UserMixin, Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    tasks = relationship('Task', back_populates='author')
    ai_config = relationship('AIConfig', back_populates='user', uselist=False)

class Task(Base):
    __tablename__ = 'task'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    user_id = Column(Integer, ForeignKey('user.id'))
    author = relationship('User', back_populates='tasks')
    submission = relationship('Submission', back_populates='task', cascade='all, delete-orphan')
    attachments = relationship('Attachment', back_populates='task', cascade='all, delete-orphan')
    task_id = Column(String(11), unique=True, default=generate_custom_id)
    analysis_report = Column(Text)
    report_file_path = Column(String(500))
    report_generated_at = Column(DateTime)

class Attachment(Base):
    __tablename__ = 'attachment'
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('task.id'), nullable=False)
    task = relationship('Task', back_populates='attachments')
    file_name = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

class Submission(Base):
    __tablename__ = 'submission'
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('task.id'))
    task = relationship('Task', back_populates='submission')
    data = Column(Text, nullable=False)
    submitted_at = Column(DateTime, default=datetime.now)

class AIConfig(Base):
    __tablename__ = 'ai_config'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), unique=True)
    user = relationship('User', back_populates='ai_config')
    selected_model = Column(String(50), default='deepseek')
    model_configs = relationship('AIModelConfig', back_populates='ai_config', cascade='all, delete-orphan')

class AIModelConfig(Base):
    __tablename__ = 'ai_model_config'
    id = Column(Integer, primary_key=True)
    ai_config_id = Column(Integer, ForeignKey('ai_config.id'))
    ai_config = relationship('AIConfig', back_populates='model_configs')
    model_name = Column(String(50))
    api_key = Column(String(200))
    api_url = Column(String(200))
    extra_settings = Column(Text)

class QFConfig(Base):
    __tablename__ = 'qf_config'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), unique=True)
    user = relationship('User', back_populates='qf_config')
    username = Column(String(100))
    password = Column(String(200))

User.qf_config = relationship('QFConfig', back_populates='user', uselist=False)

# 创建数据库表
Base.metadata.create_all(engine)

# 初始化Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 使用werkzeug.security进行密码加密（无需初始化）

@login_manager.user_loader
def load_user(user_id):
    db = SessionLocal()
    try:
        return db.query(User).get(int(user_id))
    finally:
        db.close()

def read_file_content(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return f"二进制文件 (大小: {len(content)} 字节)"
        except Exception as e:
            logger.error(f"读取文件内容失败: {str(e)}")
            return f"无法读取文件内容: {str(e)}"
    except Exception as e:
        logger.error(f"读取文件内容失败: {str(e)}")
        return f"无法读取文件内容: {str(e)}"

def generate_analysis_prompt(task, submission=None, file_content=None):
    """
    根据任务信息生成分析提示词
    """
    # 获取提交数据
    if not submission:
        db = SessionLocal()
        try:
            submission = db.query(Submission).filter_by(task_id=task.id).all()
        finally:
            db.close()
    
    # 构建提示词
    prompt = f"""你是一个数据分析专家，请基于以下表单数据提供详细的分析报告：

任务标题：{task.title}
任务描述：{task.description or '无'}

提交数据摘要：
"""
    
    # 添加提交数据摘要
    if submission:
        prompt += f"共有 {len(submission)} 条提交记录\n"
        
        # 分析前3条提交数据作为示例
        for i, sub in enumerate(submission[:3]):
            try:
                data = json.loads(sub.data)
                prompt += f"\n提交 #{i+1}:\n"
                for key, value in data.items():
                    prompt += f"  - {key}: {value}\n"
            except:
                prompt += f"\n提交 #{i+1}: {sub.data[:100]}...\n"
    else:
        prompt += "暂无提交数据\n"
    
    # 添加文件信息
    if file_content:
        prompt += f"\n附件内容摘要：\n{file_content[:500]}...\n" if len(file_content) > 500 else f"\n附件内容：\n{file_content}\n"
    
    # 添加分析要求
    prompt += """

请提供一个全面的数据分析报告，包括但不限于：
1. 数据概览：总提交量、关键数据分布等
2. 主要发现：数据中的趋势、模式和异常
3. 深入分析：基于数据的详细洞察
4. 建议和结论：基于分析结果的实用建议

请以中文撰写报告，使用Markdown格式，包括适当的标题、列表和表格来增强可读性。
"""
    
    return prompt

def call_ai_model(prompt, ai_config):
    """
    调用AI模型生成分析报告
    """
    def get_model_config(model_name):
        for mc in ai_config.model_configs:
            if mc.model_name == model_name:
                return mc
        return None

    if ai_config.selected_model == 'deepseek':
        model_cfg = get_model_config('deepseek')
        api_key = model_cfg.api_key if model_cfg else ''
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个专业的数据分析助手。请基于用户提供的数据，生成一份详细、专业、有洞察力的分析报告。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {str(e)}")
            raise Exception(f"DeepSeek API调用失败: {str(e)}")

    elif ai_config.selected_model == 'doubao':
        model_cfg = get_model_config('doubao')
        api_key = model_cfg.api_key if model_cfg else ''
        url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "doubao-seed-1-6-251015",
            "messages": [
                {"role": "system", "content": "你是一个专业的数据分析助手。请基于用户提供的数据，生成一份详细、专业、有洞察力的分析报告。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"豆包API调用失败: {str(e)}")
            raise Exception(f"豆包API调用失败: {str(e)}")

    elif ai_config.selected_model == 'qwen':
        model_cfg = get_model_config('qwen')
        api_key = model_cfg.api_key if model_cfg else ''
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "qwen-plus",
            "input": {
                "messages": [
                    {"role": "system", "content": "你是一个专业的数据分析助手。请基于用户提供的数据，生成一份详细、专业、有洞察力的分析报告。"},
                    {"role": "user", "content": prompt}
                ]
            },
            "parameters": {
                "temperature": 0.7,
                "max_tokens": 4000
            }
        }

        try:
            logger.info(f"调用阿里云百炼API，模型: qwen-plus")
            logger.info(f"请求URL: {url}")
            logger.info(f"请求头: {headers}")
            logger.info(f"请求数据: {json.dumps(data, ensure_ascii=False)[:200]}...")

            response = requests.post(url, headers=headers, json=data, timeout=120)

            logger.info(f"阿里云百炼API响应状态码: {response.status_code}")
            logger.info(f"阿里云百炼API响应头: {dict(response.headers)}")
            logger.info(f"阿里云百炼API响应内容: {response.text[:500]}...")

            if response.status_code != 200:
                raise Exception(f"阿里云百炼API调用失败，状态码: {response.status_code}，响应: {response.text[:200]}")

            if not response.text:
                raise Exception("阿里云百炼API返回空响应")

            try:
                result = response.json()
                logger.info(f"阿里云百炼API响应JSON结构: {list(result.keys()) if isinstance(result, dict) else '非字典结构'}")
            except ValueError as ve:
                raise Exception(f"阿里云百炼API返回非JSON响应: {response.text[:200]}")

            if isinstance(result, dict) and "code" in result and result["code"] != "200":
                raise Exception(f"阿里云百炼API调用失败: {result.get('message', '未知错误')} (错误码: {result.get('code')})")

            if isinstance(result, dict):
                if "output" in result and "text" in result["output"]:
                    return result["output"]["text"]
                elif "choices" in result and len(result["choices"]) > 0:
                    choice = result["choices"][0]
                    if "message" in choice and "content" in choice["message"]:
                        return choice["message"]["content"]
                    elif "text" in choice:
                        return choice["text"]
                elif "data" in result and "choices" in result["data"] and len(result["data"]["choices"]) > 0:
                    choice = result["data"]["choices"][0]
                    if "message" in choice and "content" in choice["message"]:
                        return choice["message"]["content"]

            raise Exception(f"阿里云百炼API返回未知格式的响应: {str(result)[:200]}")
        except requests.exceptions.RequestException as re:
            logger.error(f"阿里云百炼API网络请求异常: {str(re)}")
            raise Exception(f"阿里云百炼API网络请求异常: {str(re)}")
        except Exception as e:
            logger.error(f"阿里云百炼API调用失败: {str(e)}")
            raise Exception(f"阿里云百炼API调用失败: {str(e)}")

    elif ai_config.selected_model == 'glm':
        model_cfg = get_model_config('glm')
        api_key = model_cfg.api_key if model_cfg else ''
        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "glm-4",
            "messages": [
                {"role": "system", "content": "你是一个专业的数据分析助手。请基于用户提供的数据，生成一份详细、专业、有洞察力的分析报告。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }

        try:
            logger.info(f"调用GLM API，URL: {url}")
            response = requests.post(url, headers=headers, json=data, timeout=120)
            logger.info(f"GLM API响应状态码: {response.status_code}")
            logger.info(f"GLM API响应内容: {response.text[:500]}")
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"GLM API调用失败: {str(e)}")
            raise Exception(f"GLM API调用失败: {str(e)}")

    elif ai_config.selected_model == 'siliconflow':
        model_cfg = get_model_config('siliconflow')
        api_key = model_cfg.api_key if model_cfg else ''
        model_name = model_cfg.extra_settings if model_cfg and model_cfg.extra_settings else 'Qwen/Qwen2.5-72B-Instruct'
        url = "https://api.siliconflow.cn/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是一个专业的数据分析助手。请基于用户提供的数据，生成一份详细、专业、有洞察力的分析报告。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }

        try:
            logger.info(f"调用硅基流动API，URL: {url}")
            response = requests.post(url, headers=headers, json=data, timeout=120)
            logger.info(f"硅基流动API响应状态码: {response.status_code}")
            logger.info(f"硅基流动API响应内容: {response.text[:500]}")
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"硅基流动API调用失败: {str(e)}")
            raise Exception(f"硅基流动API调用失败: {str(e)}")

    elif ai_config.selected_model == 'ollama':
        model_cfg = get_model_config('ollama')
        api_url = model_cfg.api_url if model_cfg else 'http://localhost:11434'
        extra_settings = model_cfg.extra_settings if model_cfg else ''
        ollama_model = extra_settings if extra_settings else 'llama3.2'
        if not api_url.startswith('http'):
            api_url = 'http://' + api_url
        url = f"{api_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "model": ollama_model,
            "messages": [
                {"role": "system", "content": "你是一个专业的数据分析助手。请基于用户提供的数据，生成一份详细、专业、有洞察力的分析报告。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }

        try:
            logger.info(f"调用Ollama API，URL: {url}，模型: {ollama_model}")
            response = requests.post(url, headers=headers, json=data, timeout=180)
            logger.info(f"Ollama API响应状态码: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama API调用失败: {str(e)}")
            raise Exception(f"Ollama API调用失败: {str(e)}")

    else:
        raise Exception(f"不支持的AI模型: {ai_config.selected_model}")

# 创建Jinja2环境用于后台线程渲染模板
_template_env = None

def get_template_env():
    """获取Jinja2模板环境（延迟初始化）"""
    global _template_env
    if _template_env is None:
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        _template_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
    return _template_env

def save_analysis_report(task_id, report_content):
    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(id=task_id).first()
        if not task:
            return

        if not report_content or not report_content.strip():
            report_content = "本次分析未能生成有效内容。可能是由于以下原因：\n\n- 提交的数据量不足\n- 数据质量问题\n- AI模型处理异常\n\n请尝试提交更多数据或修改提示词后重新分析。"

        template = get_template_env().get_template('simple_report.html')
        html_report = template.render(task_title=task.title, report_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), report_content=report_content)

        report_dir = os.path.join(app.root_path, 'static', 'reports')
        os.makedirs(report_dir, exist_ok=True)

        if task.report_file_path and os.path.exists(task.report_file_path):
            try:
                os.remove(task.report_file_path)
            except OSError:
                pass

        report_path = os.path.join(report_dir, f"report_{task_id}.html")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_report)

        task.analysis_report = report_content
        task.report_file_path = report_path
        task.report_generated_at = datetime.now()
        db.commit()

        with progress_lock:
            completed_reports.add(task_id)

        logger.info(f"任务 {task_id} 的分析报告已保存")
    except Exception as e:
        logger.error(f"保存分析报告失败: {str(e)}")
    finally:
        db.close()

def timeout(seconds, error_message="函数执行超时"):
    """
    超时装饰器（使用线程实现，避免信号处理问题）
    """
    import threading
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 结果容器
            result = [None]
            exception = [None]
            
            # 目标函数
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
            
            # 创建并启动线程
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(seconds)
            
            # 检查线程是否仍在运行
            if thread.is_alive():
                # 线程超时，抛出异常
                raise TimeoutError(error_message)
            elif exception[0]:
                # 函数执行中出现异常
                raise exception[0]
            else:
                # 正常返回结果
                return result[0]
        
        return wrapper
    
    return decorator

def perform_analysis_with_custom_prompt(task_id, user_id, ai_config_id, custom_prompt):
    """
    使用自定义提示词执行分析任务
    """
    db = SessionLocal()
    try:
        # 获取任务信息
        task = db.query(Task).filter_by(id=task_id, user_id=user_id).first()
        if not task:
            with progress_lock:
                analysis_progress[task_id] = {
                    'status': 'error',
                    'message': '任务不存在'
                }
            return
        
        # 获取提交数据
        submission = db.query(Submission).filter_by(task_id=task_id).all()
        
        # 读取附件内容（如果有）
        file_content = None
        if task.attachments:
            # 读取第一个附件的内容
            first_attachment = task.attachments[0]
            if os.path.exists(first_attachment.file_path):
                file_content = read_file_content(first_attachment.file_path)
        
        # 获取AI配置
        ai_config = db.query(AIConfig).filter_by(id=ai_config_id).first()
        if not ai_config:
            with progress_lock:
                analysis_progress[task_id] = {
                    'status': 'error',
                    'message': 'AI配置不存在'
                }
            return
        
        # 验证AI配置是否正确
        if ai_config.selected_model == 'deepseek' and not ai_config.deepseek_api_key:
            with progress_lock:
                analysis_progress[task_id] = {
                    'status': 'error',
                    'message': 'DeepSeek API密钥未配置'
                }
            logging.error(f"任务 {task_id}：DeepSeek API密钥未配置")
            return
        elif ai_config.selected_model == 'doubao' and not ai_config.doubao_api_key:
            with progress_lock:
                analysis_progress[task_id] = {
                    'status': 'error',
                    'message': '豆包API密钥未配置完整'
                }
            logging.error(f"任务 {task_id}：豆包API密钥未配置完整")
            return
        
        logging.info(f"任务 {task_id}：使用模型 {ai_config.selected_model}")
        
        # 进度1：正在生成提示词
        with progress_lock:
            analysis_progress[task_id] = {
                'status': 'in_progress',
                'progress': 0,
                'message': '正在生成提示词...'
            }
        
        # 生成分析提示词
        prompt = custom_prompt
        
        # 进度2：大模型分析中
        with progress_lock:
            analysis_progress[task_id] = {
                'status': 'in_progress',
                'progress': 1,
                'message': '大模型分析中，这可能需要几分钟时间...'
            }
        logging.info(f"任务 {task_id}：调用AI模型进行分析")
        
        # 设置AI调用的超时时间，根据模型类型调整
        timeout_seconds = 120 if ai_config.selected_model == 'deepseek' else (120 if ai_config.selected_model == 'qwen' else 90)
        
        # 带超时的AI模型调用
        @timeout(seconds=timeout_seconds, error_message=f"调用{ai_config.selected_model}模型超时（{timeout_seconds}秒）")
        def call_ai_with_timeout(prompt, config):
            logging.info(f"开始调用 {config.selected_model} API，提示词长度: {len(prompt)} 字符，超时设置: {timeout_seconds}秒")
            return call_ai_model(prompt, config)
        
        # 调用AI模型
        try:
            analysis_report = call_ai_with_timeout(prompt, ai_config)
            logging.info(f"成功获取 {ai_config.selected_model} API 响应，报告长度: {len(analysis_report)} 字符")
        except TimeoutError as timeout_error:
            # 处理超时错误
            error_msg = str(timeout_error)
            logging.error(f"任务 {task_id}：{error_msg}")
            with progress_lock:
                analysis_progress[task_id] = {
                    'status': 'error',
                    'message': f"分析超时：{error_msg}，请检查网络连接或稍后重试"
                }
            return
        except Exception as api_error:
            logging.error(f"任务 {task_id}：AI模型调用失败: {str(api_error)}")
            logging.error(f"详细错误堆栈: {traceback.format_exc()}")
            with progress_lock:
                analysis_progress[task_id] = {
                    'status': 'error',
                    'message': f'API调用失败: {str(api_error)}'
                }
            return
        
        # 检查是否是错误消息
        if analysis_report.startswith("错误：") or \
           (analysis_report.startswith("DeepSeek API调用") and "失败" in analysis_report) or \
           (analysis_report.startswith("豆包API调用") and "失败" in analysis_report):
            logging.error(f"任务 {task_id}：AI模型返回错误: {analysis_report}")
            raise Exception(analysis_report)
        
        # 保存结果到文件和数据库
        with progress_lock:
            save_analysis_report(task_id, analysis_report)
            analysis_results[task_id] = analysis_report
            analysis_progress[task_id] = {
                'status': 'completed',
                'progress': 3,
                'message': '分析完成，请查看报告'
            }
            
    except Exception as e:
        # 处理错误
        with progress_lock:
            analysis_progress[task_id] = {
                'status': 'error',
                'message': f'分析过程中出错: {str(e)}'
            }
    finally:
        db.close()

# 路由函数
@app.route('/login', methods=['GET', 'POST'])
def login():
    # 判断是否显示 QuickForm.cn 登录选项（仅当存在默认用户且密码未修改时显示）
    show_qf_login = False
    db = SessionLocal()
    try:
        default_user = db.query(User).filter_by(username='wst').first()
        if default_user and check_password_hash(default_user.password, 'quickform'):
            show_qf_login = True
    finally:
        db.close()

    if request.method == 'POST':
        # QuickForm.cn 登录流程
        if request.form.get('qf_login'):
            qf_username = request.form.get('qf_username', '').strip()
            qf_password = request.form.get('qf_password', '').strip()

            if not qf_username or not qf_password:
                flash('请输入 QuickForm.cn 用户名和密码', 'danger')
                return render_template('login.html', show_qf_login=show_qf_login)

            try:
                response = requests.post(
                    'https://quickform.cn/cli/list',
                    json={'username': qf_username, 'password': qf_password},
                    timeout=10
                )
                result = response.json()

                if result.get('success'):
                    db = SessionLocal()
                    try:
                        # 更新本地默认用户为 QuickForm.cn 账号
                        user = db.query(User).filter_by(username='wst').first()
                        if user:
                            user.username = qf_username
                            user.password = generate_password_hash(qf_password)
                            db.commit()

                            # 同步到 QF 数据互联配置
                            qf_config = db.query(QFConfig).filter_by(user_id=user.id).first()
                            if not qf_config:
                                qf_config = QFConfig(user_id=user.id, username=qf_username, password=qf_password)
                                db.add(qf_config)
                            else:
                                qf_config.username = qf_username
                                qf_config.password = qf_password
                            db.commit()

                            login_user(user)
                            flash(_('QuickForm.cn 登录成功，已同步账号信息'), 'success')
                            next_page = request.args.get('next')
                            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
                    finally:
                        db.close()
                else:
                    flash('QuickForm.cn 认证失败: ' + result.get('message', '请检查用户名和密码'), 'danger')
            except Exception as e:
                flash('QuickForm.cn 连接失败: ' + str(e), 'danger')

            return render_template('login.html', show_qf_login=show_qf_login)

        # 本地登录流程
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(username=username).first()
            
            if user and check_password_hash(user.password, password):
                login_user(user)
                
                if password == 'quickform':
                    flash('请修改您的默认密码', 'warning')
                    return redirect(url_for('profile'))
                
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('dashboard'))
            else:
                flash('用户名或密码错误', 'danger')
        finally:
            db.close()
    
    return render_template('login.html', show_qf_login=show_qf_login)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/dashboard')
@login_required
def dashboard():
    db = SessionLocal()
    try:
        tasks = db.query(Task).filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
        return render_template('dashboard.html', tasks=tasks)
    finally:
        db.close()

@app.route('/generate_report/<int:task_id>', methods=['GET', 'POST'])
@login_required
def generate_report(task_id):
    """
    在新页面中生成分析报告
    """
    # 添加详细的请求日志
    logger.info(f"收到生成报告请求 - Task ID: {task_id}, Method: {request.method}")
    logger.info(f"请求URL: {request.url}")
    logger.info(f"请求参数: {dict(request.args)}")
    logger.info(f"表单数据: {dict(request.form)}")
    logger.info(f"请求头: {dict(request.headers)}")
    
    db = SessionLocal()
    try:
        # 检查任务权限
        task = db.query(Task).filter_by(id=task_id, user_id=current_user.id).first()
        if not task:
            logger.warning(f"任务不存在或无权访问 - Task ID: {task_id}, User ID: {current_user.id}")
            return render_template('generate_report.html', error='任务不存在或无权访问')
        
        # 获取AI配置
        ai_config = db.query(AIConfig).filter_by(user_id=current_user.id).first()
        if not ai_config or not ai_config.selected_model:
            flash('请先在配置页面设置AI模型和API密钥', 'warning')
            return redirect(url_for('profile'))
        
        # 针对不同模型验证必需的API密钥
        if ai_config.selected_model == 'deepseek' and not ai_config.deepseek_api_key:
            flash('请先配置DeepSeek API密钥', 'warning')
            return redirect(url_for('profile'))
        elif ai_config.selected_model == 'doubao' and not ai_config.doubao_api_key:
            flash('请先配置豆包API密钥', 'warning')
            return redirect(url_for('profile'))
        elif ai_config.selected_model == 'qwen' and not ai_config.qwen_api_key:
            flash('请先配置阿里云百炼API密钥', 'warning')
            return redirect(url_for('profile'))
        
        # 获取提示词
        custom_prompt = None
        if request.method == 'GET' and 'prompt' in request.args:
            custom_prompt = request.args.get('prompt')
            logger.info(f"从GET参数获取提示词，长度: {len(custom_prompt) if custom_prompt else 0}")
        elif request.method == 'POST' and 'custom_prompt' in request.form:
            custom_prompt = request.form.get('custom_prompt')
            logger.info(f"从POST表单获取提示词，长度: {len(custom_prompt) if custom_prompt else 0}")
        
        # 如果没有提示词，生成默认提示词
        if not custom_prompt:
            logger.info("未提供自定义提示词，生成默认提示词")
            submission = db.query(Submission).filter_by(task_id=task_id).all()
            file_content = None
            if task.attachments:
                # 读取第一个附件的内容
                first_attachment = task.attachments[0]
                if os.path.exists(first_attachment.file_path):
                    file_content = read_file_content(first_attachment.file_path)
            custom_prompt = generate_analysis_prompt(task, submission, file_content)
            logger.info(f"生成默认提示词，长度: {len(custom_prompt) if custom_prompt else 0}")
        else:
            logger.info(f"使用自定义提示词，长度: {len(custom_prompt)}")
        
        # 验证提示词不为空
        if not custom_prompt or not custom_prompt.strip():
            logger.warning("提示词为空或只包含空白字符")
            return render_template('generate_report.html', task=task, error="提示词不能为空", ai_config=ai_config)
        
        logger.info(f"开始生成报告任务 {task_id}，使用模型 {ai_config.selected_model}")
        
        # 执行分析
        try:
            # 进度显示
            progress_message = "正在使用AI模型分析数据..."
            
            # 设置超时时间
            timeout_seconds = 120 if ai_config.selected_model == 'deepseek' else 90
            
            # 调用AI模型
            @timeout(seconds=timeout_seconds, error_message=f"调用{ai_config.selected_model}模型超时（{timeout_seconds}秒）")
            def call_ai_with_timeout(prompt, config):
                return call_ai_model(prompt, config)
            
            # 执行分析
            analysis_report = call_ai_with_timeout(custom_prompt, ai_config)
            
            # 保存报告
            save_analysis_report(task_id, analysis_report)
            
            # 成功显示报告
            return render_template('generate_report.html', 
                                 task=task, 
                                 report=analysis_report,
                                 preview_prompt=custom_prompt,
                                 ai_config=ai_config)
            
        except Exception as e:
            logger.error(f"生成报告失败: {str(e)}")
            return render_template('generate_report.html', 
                                 task=task, 
                                 error=f'生成报告失败: {str(e)}',
                                 preview_prompt=custom_prompt,
                                 ai_config=ai_config)
            
    except Exception as e:
        logger.error(f"访问生成报告页面失败: {str(e)}")
        flash('生成报告时出现错误', 'danger')
        return redirect(url_for('task_detail', task_id=task_id))
    finally:
        db.close()

@app.route('/create_task', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        
        db = SessionLocal()
        try:
            task = Task(title=title, description=description, user_id=current_user.id)
            db.add(task)
            db.commit()
            
            # 处理多附件上传
            # 支持file、file_2、file_3等多个文件字段
            file_fields = ['file', 'file_2', 'file_3']
            for field_name in file_fields:
                if field_name in request.files and request.files[field_name].filename != '':
                    file = request.files[field_name]
                    unique_filename, filepath = save_uploaded_file(file)
                    if unique_filename:
                        attachment = Attachment(
                            task_id=task.id,
                            file_name=file.filename,
                            file_path=filepath
                        )
                        db.add(attachment)

            db.commit()
            
            flash('数据任务创建成功', 'success')
            return redirect(url_for('task_detail', task_id=task.id))
        finally:
            db.close()
    return render_template('create_task.html')

@app.route('/import_task', methods=['GET', 'POST'])
@login_required
def import_task():
    tasks = []
    error = None

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            session['quickform_username'] = username
            session['quickform_password'] = password

            url = 'https://quickform.cn/cli/list'
            data = {
                'username': username,
                'password': password
            }
            response = requests.post(url, data=data)
            response.raise_for_status()

            result = response.json()
            if result.get('success'):
                tasks = result.get('tasks', [])
            else:
                error = result.get('message', '获取任务列表失败')
        except Exception as e:
            error = f'请求失败: {str(e)}'
    else:
        tasks_param = request.args.get('tasks')
        if tasks_param:
            try:
                tasks = json.loads(tasks_param)
            except:
                tasks = []

    return render_template('import_task.html', tasks=tasks, error=error)

@app.route('/import_task_action/<string:apiid>')
@login_required
def import_task_action(apiid):
    task_name = request.args.get('task_name', '导入的任务')
    is_ajax = request.args.get('ajax') == '1'

    db = SessionLocal()
    try:
        quickform_username = session.get('quickform_username')
        quickform_password = session.get('quickform_password')

        if not quickform_username or not quickform_password:
            qf_config = db.query(QFConfig).filter_by(user_id=current_user.id).first()
            if qf_config and qf_config.username and qf_config.password:
                quickform_username = qf_config.username
                quickform_password = qf_config.password
            else:
                msg = '请先获取任务列表以验证quickform.cn账号'
                if is_ajax:
                    return jsonify({'success': False, 'message': msg})
                flash(msg, 'danger')
                return redirect(url_for('import_task'))

        quickform_url = 'https://quickform.cn'
        show_data = {
            'username': quickform_username,
            'password': quickform_password,
            'apiid': apiid
        }

        try:
            response = requests.post(
                f'{quickform_url}/cli/show',
                data=show_data,
                timeout=30,
                allow_redirects=True
            )
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"CLI show response status: {response.status_code}")
            logger.info(f"CLI show response headers: {dict(response.headers)}")
            logger.info(f"CLI show response text: {response.text[:500] if response.text else 'empty'}")

            if response.status_code != 200:
                msg = f'获取任务信息失败: HTTP {response.status_code}'
                if is_ajax:
                    return jsonify({'success': False, 'message': msg})
                flash(msg, 'danger')
                return redirect(url_for('import_task'))

            task_info = response.json()
        except json.JSONDecodeError as e:
            msg = '获取任务信息失败: 响应格式错误'
            if is_ajax:
                return jsonify({'success': False, 'message': msg})
            flash(msg, 'danger')
            return redirect(url_for('import_task'))
        except Exception as e:
            msg = f'获取任务信息失败: {str(e)}'
            if is_ajax:
                return jsonify({'success': False, 'message': msg})
            flash(msg, 'danger')
            return redirect(url_for('import_task'))

        if not task_info.get('success'):
            msg = f'获取任务信息失败: {task_info.get("message", "未知错误")}'
            if is_ajax:
                return jsonify({'success': False, 'message': msg})
            flash(msg, 'danger')
            return redirect(url_for('import_task'))

        task_title = task_info.get('name', task_name)
        task_intro = task_info.get('intro', '')
        tutorial_link = task_info.get('tutorial', '')
        share_url = task_info.get('share_url', '')
        attachments_info = task_info.get('attachments', [])

        existing_task = db.query(Task).filter_by(task_id=apiid).first()
        if existing_task:
            new_api_id = generate_custom_id()
            info_msg = f'API {apiid} 已存在，已生成新API: {new_api_id}'
            if is_ajax:
                flash(info_msg, 'info')
            else:
                flash(info_msg, 'info')
        else:
            new_api_id = apiid

        new_task = Task(
            title=task_title,
            description=task_intro,
            user_id=current_user.id,
            task_id=new_api_id
        )
        db.add(new_task)
        db.flush()

        for attachment in attachments_info:
            attachment_name = attachment.get('name', '')
            attachment_url = attachment.get('url', '')

            if not attachment_url or not attachment_name.endswith('.html'):
                continue

            try:
                html_response = requests.get(attachment_url, timeout=30)
                html_content = html_response.text

                pattern = rf'https?://quickform\.cn/api/([a-zA-Z0-9]+)'
                new_api_pattern = '/api/' + new_api_id
                modified_html = re.sub(pattern, new_api_pattern, html_content)

                short_uuid = uuid.uuid4().hex[:10]
                ext = attachment_name.rsplit('.', 1)[-1].lower() if '.' in attachment_name else ''
                short_name = attachment_name.rsplit('.', 1)[0][:10] if '.' in attachment_name else attachment_name[:10]
                unique_filename = f"{short_uuid}_{short_name}.{ext}" if ext else f"{short_uuid}_{short_name}"
                uploads_dir = os.path.join(app.root_path, 'static', 'assets')
                os.makedirs(uploads_dir, exist_ok=True)
                file_path = os.path.join(uploads_dir, unique_filename)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_html)

                relative_path = f'assets/{unique_filename}'

                db_attachment = Attachment(
                    task_id=new_task.id,
                    file_name=attachment_name,
                    file_path=relative_path
                )
                db.add(db_attachment)
            except Exception as e:
                flash(f'下载附件 {attachment_name} 失败: {str(e)}', 'warning')

        db.commit()
        success_msg = f'任务"{task_title}"导入成功，API ID: {new_api_id}'

        if is_ajax:
            return jsonify({
                'success': True,
                'message': success_msg,
                'task_id': new_task.id,
                'new_api_id': new_api_id,
                'original_apiid': apiid
            })

        flash(success_msg, 'success')
        return redirect(url_for('task_detail', task_id=new_task.id))
    except Exception as e:
        msg = f'任务导入失败: {str(e)}'
        if is_ajax:
            return jsonify({'success': False, 'message': msg})
        flash(msg, 'danger')
        return redirect(url_for('import_task'))
    finally:
        db.close()

@app.route('/import_task_by_url')
@login_required
def import_task_by_url():
    task_url = request.args.get('url', '')
    
    match = re.search(r'/api/([a-zA-Z0-9]+)', task_url)
    if not match:
        flash('无效的任务URL格式', 'danger')
        return redirect(url_for('import_task'))
    
    apiid = match.group(1)
    
    return redirect(url_for('import_task_action', apiid=apiid, task_name=f'任务{apiid}'))

@app.route('/import_task_from_file', methods=['POST'])
@login_required
def import_task_from_file():
    import zipfile
    logger = logging.getLogger(__name__)
    logger.info(f"Request files: {request.files}")
    logger.info(f"Request form: {request.form}")
    
    if 'task_file' not in request.files:
        flash('没有文件上传', 'danger')
        return redirect(url_for('import_task'))
    
    file = request.files['task_file']
    if file.filename == '':
        flash('没有选择文件', 'danger')
        return redirect(url_for('import_task'))

    try:
        zip_bytes = file.read()
        zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
        
        json_content = zip_file.read('quickform-task-migration.json').decode('utf-8')
        import json
        task_data = json.loads(json_content)
        
        original_api_id = task_data.get('api_id', '')
        title = task_data.get('title', '未命名任务')
        description = task_data.get('description', '')
        html_files = task_data.get('html_files', [])
        
        db = SessionLocal()
        try:
            existing_task = db.query(Task).filter_by(task_id=original_api_id).first()
            
            if existing_task:
                new_api_id = generate_custom_id()
                flash(f'API {original_api_id} 已存在，已生成新API: {new_api_id}', 'info')
            else:
                new_api_id = original_api_id
            
            new_task = Task(
                title=title,
                description=description,
                user_id=current_user.id,
                task_id=new_api_id
            )
            db.add(new_task)
            db.flush()
            
            for html_file_info in html_files:
                archive_name = html_file_info.get('archive_name', '')
                original_name = html_file_info.get('original_name', '')
                
                if archive_name and archive_name in zip_file.namelist():
                    html_content = zip_file.read(archive_name).decode('utf-8')

                    pattern = rf'https?://quickform\.cn/api/([a-zA-Z0-9]+)'
                    new_api_pattern = '/api/' + new_api_id
                    modified_html = re.sub(pattern, new_api_pattern, html_content)
                    
                    if original_api_id and original_api_id != new_api_id:
                        modified_html = modified_html.replace('/api/' + original_api_id, '/api/' + new_api_id)
                    
                    unique_filename = f"{uuid.uuid4().hex[:10]}_{original_name}"
                    uploads_dir = os.path.join(app.root_path, 'static', 'assets')
                    os.makedirs(uploads_dir, exist_ok=True)
                    file_path = os.path.join(uploads_dir, unique_filename)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(modified_html)
                    
                    relative_path = f'assets/{unique_filename}'
                    
                    attachment = Attachment(
                        task_id=new_task.id,
                        file_name=original_name,
                        file_path=relative_path
                    )
                    db.add(attachment)

            submissions = task_data.get('submissions', [])
            for sub_info in submissions:
                raw_data = sub_info.get('data', '{}')
                if isinstance(raw_data, dict):
                    raw_str = json.dumps(raw_data, ensure_ascii=False)
                else:
                    raw_str = str(raw_data)
                if original_api_id and original_api_id != new_api_id:
                    raw_str = raw_str.replace(original_api_id, new_api_id)
                sub = Submission(
                    task_id=new_task.id,
                    data=raw_str,
                    submitted_at=datetime.now()
                )
                db.add(sub)

            api_uploads = task_data.get('api_uploads', [])
            if api_uploads:
                upload_dir = os.path.join(app.root_path, cfg.API_UPLOAD_FOLDER, new_api_id)
                os.makedirs(upload_dir, exist_ok=True)
                for api_file_info in api_uploads:
                    arc_name = api_file_info.get('archive_name', '')
                    original_name = api_file_info.get('original_name', '')
                    if arc_name and arc_name in zip_file.namelist():
                        file_content = zip_file.read(arc_name)
                        save_path = os.path.join(upload_dir, original_name)
                        with open(save_path, 'wb') as f:
                            f.write(file_content)

            db.commit()
            flash(f'任务"{title}"导入成功，API ID: {new_api_id}', 'success')
            return redirect(url_for('task_detail', task_id=new_task.id))
        finally:
            db.close()
    except zipfile.BadZipFile:
        flash('无效的压缩包文件', 'danger')
    except KeyError as e:
        flash(f'压缩包内缺少必要文件: {str(e)}', 'danger')
    except Exception as e:
        flash(f'导入失败: {str(e)}', 'danger')
    
    return redirect(url_for('import_task'))

@app.route('/task/<int:task_id>/upload', methods=['POST'])
@login_required
def upload_task_attachment(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task:
            return jsonify({'success': False, 'message': '任务不存在'})
        if task.user_id != current_user.id:
            return jsonify({'success': False, 'message': '无权访问此任务'})

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有文件'})
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '没有选择文件'})

        unique_filename, filepath = save_uploaded_file(file)
        if unique_filename:
            attachment = Attachment(
                task_id=task.id,
                file_name=file.filename,
                file_path=filepath
            )
            db.add(attachment)
            db.commit()
            return jsonify({'success': True, 'message': '文件上传成功'})
        else:
            return jsonify({'success': False, 'message': '文件保存失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        db.close()

@app.route('/task/<int:task_id>')
@login_required
def task_detail(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task:
            flash('任务不存在', 'danger')
            return redirect(url_for('dashboard'))
        if task.user_id != current_user.id:
            flash('无权访问此任务', 'danger')
            return redirect(url_for('dashboard'))
        
        submission = db.query(Submission).filter_by(task_id=task.id).order_by(Submission.submitted_at.desc()).all()
        upload_dir = os.path.join(app.root_path, cfg.API_UPLOAD_FOLDER, task.task_id)
        has_api_uploads = os.path.exists(upload_dir) and any(os.path.isfile(os.path.join(upload_dir, f)) for f in os.listdir(upload_dir))
        return render_template('task_detail.html', task=task, submission=submission, has_api_uploads=has_api_uploads)
    finally:
        db.close()

@app.route('/task/<int:task_id>/data')
@login_required
def task_data_view(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task:
            flash('任务不存在', 'danger')
            return redirect(url_for('dashboard'))
        if task.user_id != current_user.id:
            flash('无权访问此任务', 'danger')
            return redirect(url_for('dashboard'))
        
        submission = db.query(Submission).filter_by(task_id=task.id).order_by(Submission.submitted_at.desc()).all()
        
        class SimplePagination:
            def __init__(self, page, per_page, total):
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = 1
        
        total_submissions = len(submission)
        pagination = SimplePagination(1, 10, total_submissions)
        
        return render_template('task_data_view.html', task=task, submissions=submission, total_submissions=total_submissions, pagination=pagination)
    finally:
        db.close()

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task:
            flash('任务不存在', 'danger')
            return redirect(url_for('dashboard'))
        if task.user_id != current_user.id:
            flash('无权编辑此任务', 'danger')
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            
            # 更新任务信息
            task.title = title
            task.description = description
            
            # 处理删除附件
            remove_attachments = request.form.getlist('remove_attachments')
            for attachment_id in remove_attachments:
                attachment = db.query(Attachment).get(int(attachment_id))
                if attachment and attachment.task_id == task.id:
                    physical_path = os.path.join(app.root_path, attachment.file_path)
                    if os.path.exists(physical_path):
                        os.remove(physical_path)
                    db.delete(attachment)
            
            # 处理新附件上传
            # 支持file、file_2、file_3等多个文件字段
            file_fields = ['file', 'file_2', 'file_3']
            for field_name in file_fields:
                if field_name in request.files and request.files[field_name].filename != '':
                    file = request.files[field_name]
                    unique_filename, filepath = save_uploaded_file(file)
                    if unique_filename:
                        attachment = Attachment(
                            task_id=task.id,
                            file_name=file.filename,
                            file_path=filepath
                        )
                        db.add(attachment)
            
            db.commit()
            flash('任务更新成功', 'success')
            return redirect(url_for('task_detail', task_id=task.id))
        
        return render_template('edit_task.html', task=task)
    finally:
        db.close()

@app.route('/delete_submission/<int:submission_id>', methods=['POST', 'GET'])
@login_required
def delete_submission(submission_id):
    """删除单个提交数据"""
    db = SessionLocal()
    try:
        submission = db.query(Submission).get(submission_id)
        if not submission:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '提交数据不存在'})
            flash('提交数据不存在', 'danger')
            return redirect(url_for('dashboard'))
        
        task = db.query(Task).get(submission.task_id)
        if not task:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '任务不存在'})
            flash('任务不存在', 'danger')
            return redirect(url_for('dashboard'))
        
        if task.user_id != current_user.id:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '无权删除此提交数据'})
            flash('无权删除此提交数据', 'danger')
            return redirect(url_for('dashboard'))
        
        db.delete(submission)
        db.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': '提交数据已删除'})
        
        flash('提交数据已删除', 'success')
        return redirect(url_for('task_data_view', task_id=task.id))
    finally:
        db.close()

@app.route('/clear_all_submissions/<int:task_id>', methods=['GET'])
@login_required
def clear_all_submissions(task_id):
    """清空所有提交数据"""
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '任务不存在'})
            flash('任务不存在', 'danger')
            return redirect(url_for('dashboard'))
        
        if task.user_id != current_user.id:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '无权删除此任务数据'})
            flash('无权删除此任务数据', 'danger')
            return redirect(url_for('dashboard'))
        
        db.query(Submission).filter_by(task_id=task.id).delete()
        db.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': '已清空所有提交数据'})
        
        flash('已清空所有提交数据', 'success')
        return redirect(url_for('task_data_view', task_id=task.id))
    finally:
        db.close()

@app.route('/delete_multiple_submissions/<int:task_id>', methods=['POST'])
@login_required
def delete_multiple_submissions(task_id):
    """批量删除提交数据"""
    db = SessionLocal()
    try:
        # 查询任务
        task = db.query(Task).get(task_id)
        if not task:
            flash('任务不存在', 'danger')
            return redirect(url_for('dashboard'))
        
        # 检查用户权限
        if task.user_id != current_user.id:
            flash('无权删除此任务的提交数据', 'danger')
            return redirect(url_for('dashboard'))
        
        # 获取要删除的提交数据ID列表
        submission_ids = request.form.getlist('submission_ids')
        if not submission_ids:
            flash('请选择要删除的提交数据', 'warning')
            return redirect(url_for('task_detail', task_id=task_id))
        
        # 转换为整数并过滤
        submission_ids = [int(sid) for sid in submission_ids if sid.isdigit()]
        
        # 查询这些提交数据
        submissions = db.query(Submission).filter(
            Submission.id.in_(submission_ids),
            Submission.task_id == task_id
        ).all()
        
        # 检查是否所有提交数据都属于当前用户
        for sub in submissions:
            if sub.task.user_id != current_user.id:
                flash('无权删除部分提交数据', 'danger')
                return redirect(url_for('task_detail', task_id=task_id))
        
        # 删除提交数据
        for submission in submissions:
            db.delete(submission)
        
        db.commit()
        flash(f'已删除 {len(submissions)} 条提交数据', 'success')
        return redirect(url_for('task_detail', task_id=task_id))
    except ValueError:
        flash('无效的提交数据ID', 'danger')
        return redirect(url_for('task_detail', task_id=task_id))
    finally:
        db.close()

@app.route('/delete_attachment/<int:attachment_id>', methods=['POST'])
@login_required
def delete_attachment(attachment_id):
    import os
    db = SessionLocal()
    try:
        attachment = db.query(Attachment).get(attachment_id)
        if not attachment:
            return jsonify({'success': False, 'message': '附件不存在'})
        
        task = db.query(Task).get(attachment.task_id)
        if not task or task.user_id != current_user.id:
            return jsonify({'success': False, 'message': '无权删除此附件'})
        
        file_path = attachment.file_path
        physical_path = os.path.join(app.root_path, file_path)
        if os.path.exists(physical_path):
            os.remove(physical_path)
        
        db.delete(attachment)
        db.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        db.close()

@app.route('/get_attachment_content/<int:attachment_id>')
@login_required
def get_attachment_content(attachment_id):
    db = SessionLocal()
    try:
        attachment = db.query(Attachment).get(attachment_id)
        if not attachment:
            return jsonify({'success': False, 'message': '附件不存在'})

        task = db.query(Task).get(attachment.task_id)
        if not task or task.user_id != current_user.id:
            return jsonify({'success': False, 'message': '无权访问此附件'})

        ext = attachment.file_name.rsplit('.', 1)[-1].lower() if '.' in attachment.file_name else ''
        if ext not in ('html', 'htm'):
            return jsonify({'success': False, 'message': '仅支持编辑 HTML/HTM 文件'})

        physical_path = os.path.join(app.root_path, attachment.file_path)
        if not os.path.exists(physical_path):
            return jsonify({'success': False, 'message': '文件不存在'})

        with open(physical_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return jsonify({
            'success': True,
            'file_name': attachment.file_name,
            'content': content
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        db.close()

@app.route('/save_attachment_content/<int:attachment_id>', methods=['POST'])
@login_required
def save_attachment_content(attachment_id):
    db = SessionLocal()
    try:
        attachment = db.query(Attachment).get(attachment_id)
        if not attachment:
            return jsonify({'success': False, 'message': '附件不存在'})

        task = db.query(Task).get(attachment.task_id)
        if not task or task.user_id != current_user.id:
            return jsonify({'success': False, 'message': '无权编辑此附件'})

        ext = attachment.file_name.rsplit('.', 1)[-1].lower() if '.' in attachment.file_name else ''
        if ext not in ('html', 'htm'):
            return jsonify({'success': False, 'message': '仅支持编辑 HTML/HTM 文件'})

        physical_path = os.path.join(app.root_path, attachment.file_path)
        content = request.json.get('content', '')

        with open(physical_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return jsonify({'success': True, 'message': '保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        db.close()

@app.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    import os
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task:
            flash('任务不存在', 'danger')
            return redirect(url_for('dashboard'))
        if task.user_id != current_user.id:
            flash('无权删除此任务', 'danger')
            return redirect(url_for('dashboard'))
        
        attachments = db.query(Attachment).filter_by(task_id=task.id).all()
        for attachment in attachments:
            file_path = os.path.join(app.root_path, attachment.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        upload_dir = os.path.join(app.root_path, cfg.API_UPLOAD_FOLDER, task.task_id)
        if os.path.exists(upload_dir):
            import shutil
            shutil.rmtree(upload_dir)
        
        report_dir = os.path.join(app.root_path, 'static', 'reports')
        report_path = os.path.join(report_dir, f"report_{task.id}.html")
        if os.path.exists(report_path):
            os.remove(report_path)
        
        db.delete(task)
        db.commit()
        flash('任务已删除', 'success')
        return redirect(url_for('dashboard'))
    finally:
        db.close()

@app.route('/test_api_key', methods=['POST', 'OPTIONS'])
@login_required
def test_api_key():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    try:
        data = request.get_json()
        model = data.get('model')
        api_key = data.get('api_key', '')
        api_url = data.get('api_url', '')
        model_name = data.get('model_name', '')

        if not model:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400

        class TestModelConfig:
            def __init__(self, model_name, api_key, api_url, extra_settings):
                self.model_name = model_name
                self.api_key = api_key
                self.api_url = api_url
                self.extra_settings = extra_settings

        class TestAIConfig:
            def __init__(self, model, api_key, api_url, model_name):
                self.selected_model = model
                self.model_configs = [TestModelConfig(model, api_key, api_url, model_name or ('llama3.2' if model == 'ollama' else ''))]

        test_config = TestAIConfig(model, api_key, api_url, model_name)

        test_prompt = '这是一个API密钥测试，请回复"测试成功"'

        result = call_ai_model(test_prompt, test_config)

        if result and ('测试成功' in result or 'success' in result.lower()):
            return jsonify({'success': True, 'message': 'API密钥有效'}), 200
        else:
            return jsonify({'success': True, 'message': 'API密钥有效，但返回内容不符合预期'}), 200

    except Exception as e:
        logger.error(f"API密钥测试失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/qrcode')
@login_required
def generate_qrcode():
    import qrcode as qr_lib
    data = request.args.get('data', '')
    if not data:
        return 'Missing data parameter', 400
    img = qr_lib.make(data, error_correction=qr_lib.constants.ERROR_CORRECT_L)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

def _get_all_submissions_response(task_id):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(task_id=task_id).first()
        if not task:
            response = jsonify({'error': '任务不存在'})
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response, 404

        submissions = db.query(Submission).filter_by(task_id=task.id).all()
        all_data = []
        for sub in submissions:
            try:
                data = json.loads(sub.data)
            except:
                try:
                    import ast
                    data = ast.literal_eval(sub.data)
                except:
                    data = {'raw_data': str(sub.data)}
            if isinstance(data, dict):
                data['submitted_at'] = sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S')
                all_data.append(data)
            elif isinstance(data, list):
                all_data.append({'items': data, 'submitted_at': sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S')})

        submission_count = len(all_data)
        response_data = {
            'note': f'Total {submission_count} submission(s).',
            'submissions': all_data,
            'task_id': task_id,
            'task_title': task.title,
            'total_submissions': submission_count
        }
        json_response = json.dumps(response_data, ensure_ascii=False, sort_keys=False)
        response = make_response(json_response)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    finally:
        db.close()

@app.route('/api/<string:task_id>/all', methods=['GET', 'OPTIONS'])
def get_all_submissions(task_id):
    return _get_all_submissions_response(task_id)

@app.route('/api/<string:task_id>/count', methods=['GET'])
def get_submission_count(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(task_id=task_id).first()
        if not task:
            response = jsonify({'error': '任务不存在'})
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response, 404

        total = db.query(Submission).filter_by(task_id=task.id).count()
        base_url = request.host_url.rstrip('/')

        data = {
            'task_id': task_id,
            'task_title': task.title,
            'total_submissions': total,
            'all_url': f'{base_url}/api/{task_id}/all',
            'note': f'Lightweight counter for polling. When total_submissions increases, fetch full JSON from {base_url}/api/{task_id}/all.'
        }

        response = jsonify(data)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    finally:
        db.close()

@app.route('/api/<string:task_id>', methods=['GET', 'POST', 'OPTIONS'])
def submit_form(task_id):
    if request.method in ('GET', 'OPTIONS'):
        return _get_all_submissions_response(task_id)

    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(task_id=task_id).first()
        if not task:
            response = jsonify({'error': '任务不存在'})
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response, 404
        
        # 获取客户端IP地址
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # 处理POST请求 - 回收数据
        form_data = {}
        import json
        
        # 检查Content-Type并选择合适的数据获取方式
        if request.is_json:
            # 如果是JSON请求，尝试获取JSON数据
            try:
                form_data = request.get_json() or {}
            except Exception as e:
                logger.error(f"解析JSON数据失败: {str(e)}")
                form_data = {}
        else:
            # 如果不是JSON请求，获取表单数据
            form_data = request.form.to_dict()
        
        # 如果表单数据仍然为空，尝试从请求体获取原始数据
        if not form_data:
            try:
                form_data = request.get_data(as_text=True)
            except Exception as e:
                logger.error(f"获取请求体数据失败: {str(e)}")
                form_data = {}

        # 处理文件上传
        import uuid
        uploaded_files = []
        file_upload_rejected = False
        file_size_rejected = False
        file_type_rejected = False
        if request.files:
            if cfg.API_FILE_UPLOAD_ENABLED:
                max_size_bytes = cfg.DEFAULT_MAX_FILE_SIZE * 1024 * 1024
                allowed = cfg.DEFAULT_ALLOWED_EXTENSIONS
                allowed_exts = [e.strip().lower() for e in allowed.split(',') if e.strip()]
                
                upload_dir = os.path.join(app.root_path, cfg.API_UPLOAD_FOLDER, task_id)
                os.makedirs(upload_dir, exist_ok=True)
                for file_key in request.files:
                    file = request.files[file_key]
                    if file and file.filename:
                        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                        if allowed_exts and ext and ext not in allowed_exts:
                            file_type_rejected = True
                            continue
                        file.seek(0, 2)
                        file_size = file.tell()
                        file.seek(0)
                        if file_size > max_size_bytes:
                            file_size_rejected = True
                            continue
                        random_name = uuid.uuid4().hex[:10] + (f'.{ext}' if ext else '')
                        file_path = os.path.join(upload_dir, random_name)
                        file.save(file_path)
                        relative_path = f'/{cfg.API_UPLOAD_FOLDER}/{task_id}/{random_name}'
                        uploaded_files.append(relative_path)
                
                if uploaded_files:
                    if isinstance(form_data, dict):
                        form_data['attachment'] = uploaded_files[0] if len(uploaded_files) == 1 else uploaded_files
                    elif isinstance(form_data, str):
                        try:
                            parsed = json.loads(form_data)
                            if isinstance(parsed, dict):
                                parsed['attachment'] = uploaded_files[0] if len(uploaded_files) == 1 else uploaded_files
                                form_data = parsed
                            else:
                                form_data = {'data': form_data, 'attachment': uploaded_files[0] if len(uploaded_files) == 1 else uploaded_files}
                        except:
                            form_data = {'data': form_data, 'attachment': uploaded_files[0] if len(uploaded_files) == 1 else uploaded_files}
            else:
                for file_key in request.files:
                    file = request.files[file_key]
                    if file and file.filename:
                        file_upload_rejected = True
                        break
        
        # 自动添加IP地址到数据包
        if isinstance(form_data, dict):
            form_data['_ip'] = client_ip
        elif isinstance(form_data, str):
            try:
                parsed = json.loads(form_data)
                if isinstance(parsed, dict):
                    parsed['_ip'] = client_ip
                    form_data = parsed
                else:
                    form_data = {'data': form_data, '_ip': client_ip}
            except:
                form_data = {'data': form_data, '_ip': client_ip}
        
        submission = Submission(task_id=task.id, data=json.dumps(form_data, ensure_ascii=False) if isinstance(form_data, dict) else str(form_data))
        db.add(submission)
        db.commit()
        
        response_data = {'message': '提交成功'}
        if uploaded_files:
            response_data['attachment'] = uploaded_files[0] if len(uploaded_files) == 1 else uploaded_files
        warnings = []
        if file_upload_rejected:
            warnings.append(_('文件上传功能已关闭，文件未保存'))
        if file_size_rejected:
            warnings.append(_('部分文件超过大小限制，未保存'))
        if file_type_rejected:
            warnings.append(_('部分文件类型不支持，未保存'))
        if warnings:
            response_data['warning'] = '; '.join(warnings)
        response = jsonify(response_data)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
    finally:
        db.close()

@app.route('/export/<int:task_id>')
@login_required
def export_data(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task or task.user_id != current_user.id:
            flash('无权访问此数据', 'danger')
            return redirect(url_for('dashboard'))
        
        submission = db.query(Submission).filter_by(task_id=task.id).all()
        
        if not submission:
            flash('没有可导出的数据', 'info')
            return redirect(url_for('task_detail', task_id=task_id))
        
        # 尝试解析提交数据并转换为DataFrame
        data_list = []
        for sub in submission:
            try:
                data = json.loads(sub.data)
                data['submitted_at'] = sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S')
                data_list.append(data)
            except:
                # 如果解析失败，添加原始数据
                data_list.append({
                    'submitted_at': sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'raw_data': sub.data
                })
        
        df = pd.DataFrame(data_list)
        
        # 创建CSV文件
        output = io.BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        # 发送文件（兼容不同版本的Flask）
        filename = f"{task.title}_数据导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            # 尝试使用新版本Flask的参数
            return send_file(output, download_name=filename, as_attachment=True, mimetype='text/csv; charset=utf-8')
        except TypeError:
            # 如果新参数不被支持，回退到旧版本的参数
            return send_file(output, attachment_filename=filename, as_attachment=True, mimetype='text/csv; charset=utf-8')
    except Exception as e:
        flash(f'导出数据时出错: {str(e)}', 'danger')
        return redirect(url_for('task_detail', task_id=task_id))
    finally:
        db.close()

@app.route('/export_json/<int:task_id>')
@login_required
def export_json(task_id):
    """
    导出任务提交数据为JSON格式
    """
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task or task.user_id != current_user.id:
            flash('无权访问此数据', 'danger')
            return redirect(url_for('dashboard'))
        
        submission = db.query(Submission).filter_by(task_id=task.id).all()
        
        if not submission:
            flash('没有可导出的数据', 'info')
            return redirect(url_for('task_detail', task_id=task_id))
        
        # 构建JSON数据
        data_list = []
        for sub in submission:
            try:
                data = json.loads(sub.data)
                data['_submitted_at'] = sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S')
                data['_submission_id'] = sub.id
                data_list.append(data)
            except:
                # 如果解析失败，添加原始数据
                data_list.append({
                    '_submitted_at': sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                    '_submission_id': sub.id,
                    '_raw_data': sub.data
                })
        
        # 创建JSON输出
        output = io.BytesIO()
        json_data = {
            'task_title': task.title,
            'task_id': task.id,
            'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_records': len(data_list),
            'data': data_list
        }
        output.write(json.dumps(json_data, ensure_ascii=False, indent=2).encode('utf-8'))
        output.seek(0)
        
        # 发送文件（兼容不同版本的Flask）
        filename = f"{task.title}_数据导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            # 尝试使用新版本Flask的参数
            return send_file(output, download_name=filename, as_attachment=True, mimetype='application/json; charset=utf-8')
        except TypeError:
            # 如果新参数不被支持，回退到旧版本的参数
            return send_file(output, attachment_filename=filename, as_attachment=True, mimetype='application/json; charset=utf-8')
    except Exception as e:
        flash(f'导出数据时出错: {str(e)}', 'danger')
        return redirect(url_for('task_detail', task_id=task_id))
    finally:
        db.close()

@app.route('/export_task/<int:task_id>')
@login_required
def export_task(task_id):
    import zipfile
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task or task.user_id != current_user.id:
            flash('无权访问此任务', 'danger')
            return redirect(url_for('dashboard'))

        include_submissions = request.args.get('include_submissions') == '1'
        include_api_uploads = request.args.get('include_api_uploads') == '1'

        safe_title = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', task.title)
        zip_filename = f'{safe_title}_task_export.zip'

        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
            html_files_meta = []
            attachments = db.query(Attachment).filter_by(task_id=task.id).all()
            for idx, att in enumerate(attachments):
                abs_path = os.path.join(app.root_path, att.file_path)
                if os.path.exists(abs_path):
                    ext = att.file_name.rsplit('.', 1)[-1] if '.' in att.file_name else 'html'
                    archive_name = f'html_files/{idx + 1}_{att.file_name}'
                    zf.write(abs_path, archive_name)
                    html_files_meta.append({
                        'archive_name': archive_name,
                        'original_name': att.file_name
                    })

            task_data = {
                'api_id': task.task_id,
                'title': task.title,
                'description': task.description or '',
                'html_files': html_files_meta
            }

            if include_submissions:
                submissions = db.query(Submission).filter_by(task_id=task.id).all()
                sub_list = []
                for sub in submissions:
                    sub_list.append({
                        'data': sub.data,
                        'submitted_at': sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S')
                    })
                task_data['submissions'] = sub_list

            if include_api_uploads:
                upload_dir = os.path.join(app.root_path, cfg.API_UPLOAD_FOLDER, task.task_id)
                api_files = []
                if os.path.exists(upload_dir):
                    for fname in os.listdir(upload_dir):
                        fpath = os.path.join(upload_dir, fname)
                        if os.path.isfile(fpath):
                            arc_name = f'api_uploads/{fname}'
                            zf.write(fpath, arc_name)
                            api_files.append({'archive_name': arc_name, 'original_name': fname})
                task_data['api_uploads'] = api_files

            zf.writestr('quickform-task-migration.json', json.dumps(task_data, ensure_ascii=False, indent=2))

        output.seek(0)
        return send_file(output, as_attachment=True, download_name=zip_filename, mimetype='application/zip')
    except Exception as e:
        flash(f'导出任务时出错: {str(e)}', 'danger')
        return redirect(url_for('task_detail', task_id=task_id))
    finally:
        db.close()

@app.route('/api/qf/test_connection', methods=['POST'])
@login_required
def test_qf_connection():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'success': False, 'message': '请输入用户名和密码'})

    try:
        response = requests.post(
            'https://quickform.cn/cli/list',
            json={'username': username, 'password': password},
            timeout=10
        )
        result = response.json()
        if result.get('success'):
            return jsonify({'success': True, 'message': '连接成功', 'tasks': result.get('tasks', [])})
        else:
            return jsonify({'success': False, 'message': result.get('message', '认证失败')})
    except Exception as e:
        return jsonify({'success': False, 'message': f'连接失败: {str(e)}'})

@app.route('/api/qf/import_data', methods=['POST'])
@login_required
def import_qf_data():
    data = request.get_json()
    task_id = data.get('task_id')
    apiid = data.get('apiid')

    if not task_id or not apiid:
        return jsonify({'success': False, 'message': '缺少参数'})

    db = SessionLocal()
    try:
        task = db.query(Task).get(int(task_id))
        if not task or task.user_id != current_user.id:
            return jsonify({'success': False, 'message': '任务不存在或无权访问'})

        try:
            response = requests.get(
                f'https://quickform.cn/api/{apiid}/all',
                timeout=30,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; QuickForm/3.0)'}
            )

            if response.status_code != 200:
                return jsonify({'success': False, 'message': f'获取数据失败: HTTP {response.status_code}'})

            result = response.json()
            submissions = result.get('submissions', [])

            if not submissions:
                return jsonify({'success': False, 'message': '该任务暂无数据'})

            imported_count = 0
            for sub in submissions:
                if isinstance(sub, dict):
                    submission_data = json.dumps(sub, ensure_ascii=False)
                else:
                    submission_data = str(sub)

                new_submission = Submission(
                    task_id=task.id,
                    data=str(submission_data)
                )
                db.add(new_submission)
                imported_count += 1

            db.commit()
            return jsonify({'success': True, 'message': f'成功导入 {imported_count} 条数据', 'count': imported_count})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'获取数据失败: {str(e)}'})
    finally:
        db.close()

@app.route('/api/qf/list', methods=['GET'])
@login_required
def get_qf_task_list():
    db = SessionLocal()
    try:
        qf_config = db.query(QFConfig).filter_by(user_id=current_user.id).first()
        if not qf_config or not qf_config.username or not qf_config.password:
            return jsonify({'success': False, 'message': '请先在设置中配置QFLink'})

        try:
            response = requests.post(
                'https://quickform.cn/cli/list',
                json={'username': qf_config.username, 'password': qf_config.password},
                timeout=10
            )
            result = response.json()
            if result.get('success'):
                return jsonify({'success': True, 'tasks': result.get('tasks', [])})
            else:
                return jsonify({'success': False, 'message': result.get('message', '认证失败')})
        except Exception as e:
            return jsonify({'success': False, 'message': f'连接失败: {str(e)}'})
    finally:
        db.close()

@app.route('/api/system/init', methods=['POST'])
@login_required
def system_init():
    import os
    db = SessionLocal()
    try:
        try:
            ai_config = db.query(AIConfig).filter_by(user_id=current_user.id).first()
            if ai_config:
                db.query(AIModelConfig).filter(
                    AIModelConfig.ai_config_id == ai_config.id,
                    AIModelConfig.model_name != 'ollama'
                ).delete(synchronize_session=False)
                ollama_cfg = db.query(AIModelConfig).filter(
                    AIModelConfig.ai_config_id == ai_config.id,
                    AIModelConfig.model_name == 'ollama'
                ).first()
                if ollama_cfg:
                    ollama_cfg.api_key = ''
                if not ollama_cfg:
                    ollama_cfg = AIModelConfig(
                        ai_config_id=ai_config.id,
                        model_name='ollama',
                        api_key='',
                        api_url='http://localhost:11434',
                        extra_settings='llama3'
                    )
                    db.add(ollama_cfg)
            
            qf_configs = db.query(QFConfig).filter_by(user_id=current_user.id).all()
            for qf in qf_configs:
                db.delete(qf)
            
            user = db.query(User).filter_by(id=current_user.id).first()
            if user:
                user.username = 'wst'
                user.password = generate_password_hash('quickform')
            
            all_tasks = db.query(Task).filter_by(user_id=current_user.id).order_by(Task.id).all()
            tasks_to_delete = all_tasks[3:] if len(all_tasks) > 3 else []
            
            for task in tasks_to_delete:
                attachments = db.query(Attachment).filter_by(task_id=task.id).all()
                for att in attachments:
                    if os.path.exists(att.file_path):
                        os.remove(att.file_path)
                    db.delete(att)
                db.delete(task)
            
            import secrets
            new_secret_key = secrets.token_hex(32)
            
            env_path = os.path.join(app.root_path, '.env')
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    env_content = f.read()
                env_content = re.sub(
                    r'SECRET_KEY\s*=\s*[^\n]*',
                    f'SECRET_KEY={new_secret_key}',
                    env_content
                )
            else:
                env_content = f'SECRET_KEY={new_secret_key}\n'
            
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(env_content)
            
            app.config['SECRET_KEY'] = new_secret_key
            
            db.commit()
            return jsonify({'success': True, 'message': '系统初始化成功，SECRET_KEY 已更新'})
        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'message': f'初始化失败: {str(e)}'})
    finally:
        db.close()

@app.route('/api/backup')
@login_required
def backup_data():
    import zipfile
    from datetime import datetime

    backup_dir = os.path.join(app.root_path, 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f'quickform_backup_{timestamp}.zip'
    zip_path = os.path.join(backup_dir, zip_filename)

    db_path = os.path.join(app.root_path, 'data', 'quickform.db')
    assets_dir = os.path.join(app.root_path, cfg.UPLOAD_FOLDER)
    uploads_dir = os.path.join(app.root_path, cfg.API_UPLOAD_FOLDER)
    reports_dir = os.path.join(app.root_path, 'static', 'reports')

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(db_path):
            zf.write(db_path, 'data/quickform.db')

        for dir_label, dir_path in [('static/assets', assets_dir), ('static/uploads', uploads_dir), ('static/reports', reports_dir)]:
            if os.path.exists(dir_path):
                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        full = os.path.join(root, file)
                        arc = os.path.join(dir_label, os.path.relpath(full, dir_path))
                        zf.write(full, arc)

    file_size = os.path.getsize(zip_path)
    size_str = f'{file_size / 1024:.1f} KB' if file_size < 1024 * 1024 else f'{file_size / (1024 * 1024):.1f} MB'

    return jsonify({
        'success': True,
        'filename': zip_filename,
        'path': f'backups/{zip_filename}',
        'size': size_str
    })

@app.route('/api/backup/download/<filename>')
@login_required
def download_backup(filename):
    backup_dir = os.path.join(app.root_path, 'backups')
    safe_name = os.path.basename(filename)
    file_path = os.path.join(backup_dir, safe_name)
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'message': '文件不存在'}), 404
    return send_file(file_path, as_attachment=True, download_name=safe_name, mimetype='application/zip')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = SessionLocal()
    try:
        ai_config = db.query(AIConfig).filter_by(user_id=current_user.id).first()

        if request.method == 'POST':
            if 'selected_model' in request.form:
                selected_model = request.form.get('selected_model')

                if not ai_config:
                    ai_config = AIConfig(user_id=current_user.id, selected_model=selected_model)
                    db.add(ai_config)
                    db.flush()
                else:
                    ai_config.selected_model = selected_model

                db.query(AIModelConfig).filter_by(ai_config_id=ai_config.id).delete()

                model_configs = [
                    ('deepseek', request.form.get('deepseek_api_key', ''), '', ''),
                    ('doubao', request.form.get('doubao_api_key', ''), '', ''),
                    ('qwen', request.form.get('qwen_api_key', ''), '', ''),
                    ('glm', request.form.get('glm_api_key', ''), '', ''),
                    ('siliconflow', request.form.get('siliconflow_api_key', ''), '', request.form.get('siliconflow_model', 'Qwen/Qwen2.5-72B-Instruct')),
                    ('ollama', '', request.form.get('ollama_api_url', 'http://localhost:11434'), request.form.get('ollama_model', 'llama3.2')),
                ]

                for model_name, api_key, api_url, extra_settings in model_configs:
                    if api_key or api_url:
                        model_cfg = AIModelConfig(
                            ai_config_id=ai_config.id,
                            model_name=model_name,
                            api_key=api_key,
                            api_url=api_url,
                            extra_settings=extra_settings
                        )
                        db.add(model_cfg)

                db.commit()
                flash('AI配置更新成功', 'success')

            elif 'update_qf_config' in request.form:
                qf_username = request.form.get('qf_username', '').strip()
                qf_password = request.form.get('qf_password', '').strip()
                
                qf_config = db.query(QFConfig).filter_by(user_id=current_user.id).first()
                if not qf_config:
                    qf_config = QFConfig(user_id=current_user.id, username=qf_username, password=qf_password)
                    db.add(qf_config)
                else:
                    qf_config.username = qf_username
                    qf_config.password = qf_password
                
                db.commit()
                flash('QF配置更新成功', 'success')

            elif 'change_username' in request.form:
                new_username = request.form.get('username', '').strip()
                user = db.query(User).filter_by(id=current_user.id).first()
                if user and new_username:
                    user.username = new_username
                    db.commit()
                    flash('用户名修改成功', 'success')
                else:
                    flash('用户名修改失败', 'danger')

            elif 'change_password' in request.form:
                current_password = request.form.get('current_password')
                new_password = request.form.get('new_password')

                user = db.query(User).filter_by(id=current_user.id).first()
                if user and check_password_hash(user.password, current_password):
                    user.password = generate_password_hash(new_password)
                    db.commit()
                    flash('密码修改成功', 'success')
                else:
                    flash('当前密码错误', 'danger')

            elif 'update_upload_settings' in request.form:
                max_file_size = request.form.get('max_file_size', str(cfg.DEFAULT_MAX_FILE_SIZE)).strip()
                allowed_extensions = request.form.get('allowed_extensions', cfg.DEFAULT_ALLOWED_EXTENSIONS).strip()
                api_file_upload_enabled = 'api_file_upload_enabled' in request.form
                try:
                    max_file_size = int(max_file_size)
                except:
                    max_file_size = cfg.DEFAULT_MAX_FILE_SIZE

                # 同步更新 config.py 文件并重新加载模块
                try:
                    config_path = os.path.join(app.root_path, 'config.py')
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_content = f.read()

                    # 更新 DEFAULT_MAX_FILE_SIZE
                    config_content = re.sub(
                        r"DEFAULT_MAX_FILE_SIZE\s*=\s*\d+",
                        f"DEFAULT_MAX_FILE_SIZE = {max_file_size}",
                        config_content
                    )

                    # 更新 DEFAULT_ALLOWED_EXTENSIONS
                    config_content = re.sub(
                        r"DEFAULT_ALLOWED_EXTENSIONS\s*=\s*'[^']*'",
                        f"DEFAULT_ALLOWED_EXTENSIONS = '{allowed_extensions}'",
                        config_content
                    )

                    # 更新 API_FILE_UPLOAD_ENABLED
                    config_content = re.sub(
                        r"API_FILE_UPLOAD_ENABLED\s*=\s*(True|False)",
                        f"API_FILE_UPLOAD_ENABLED = {api_file_upload_enabled}",
                        config_content
                    )

                    with open(config_path, 'w', encoding='utf-8') as f:
                        f.write(config_content)

                    # 重新加载 config 模块，使修改立即生效
                    import importlib
                    importlib.reload(cfg)
                    flash('上传文件设置保存成功', 'success')
                except Exception as e:
                    flash(f'配置文件更新失败: {str(e)}', 'warning')

            active_tab = request.form.get('active_tab', 'config')
            return redirect(url_for('profile', active_tab=active_tab))

        model_configs_dict = {}
        if ai_config:
            for mc in ai_config.model_configs:
                model_configs_dict[mc.model_name] = mc

        qf_config = db.query(QFConfig).filter_by(user_id=current_user.id).first()

        return render_template('profile.html', user=current_user, ai_config=ai_config, model_configs_dict=model_configs_dict, qf_config=qf_config, upload_default_max_size=cfg.DEFAULT_MAX_FILE_SIZE, upload_default_extensions=cfg.DEFAULT_ALLOWED_EXTENSIONS, api_file_upload_enabled=cfg.API_FILE_UPLOAD_ENABLED)
    finally:
        db.close()

@app.route('/analyze/<int:task_id>/smart_analyze', methods=['GET'])
@login_required
def smart_analyze(task_id):
    """
    智能分析页面 - 显示分析选项和数据统计
    """
    db = SessionLocal()
    try:
        # 检查用户是否拥有该任务
        task = db.query(Task).filter_by(id=task_id, user_id=current_user.id).first()
        if not task:
            flash('任务不存在', 'danger')
            return redirect(url_for('dashboard'))
        
        # 获取提交数据数量和列表
        submission = db.query(Submission).filter_by(task_id=task_id).all()
        submission_count = len(submission)
        
        # 检查是否有AI配置
        ai_config = db.query(AIConfig).filter_by(user_id=current_user.id).first()
        
        # 检查是否有APIKEY
        has_api_key = False
        if ai_config and ai_config.selected_model:
            model_cfg = db.query(AIModelConfig).filter_by(
                ai_config_id=ai_config.id,
                model_name=ai_config.selected_model
            ).first()
            if model_cfg:
                if model_cfg.api_key:
                    has_api_key = True
                elif model_cfg.api_url and ai_config.selected_model == 'ollama':
                    has_api_key = True
        
        # 读取附件内容（如果有）
        file_content = None
        if task.attachments:
            # 读取第一个附件的内容
            first_attachment = task.attachments[0]
            if os.path.exists(first_attachment.file_path):
                file_content = read_file_content(first_attachment.file_path)
        
        # 生成预览提示词
        preview_prompt = generate_analysis_prompt(task, submission, file_content)
        
        # 获取报告内容（如果存在）
        report = task.analysis_report if task and task.analysis_report else None
        
        sample_submissions = []
        for sub in submission[:3]:
            try:
                data = json.loads(sub.data)
            except:
                data = {'raw_data': str(sub.data)}
            if isinstance(data, dict):
                data['submitted_at'] = sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S')
            sample_submissions.append(data)
        
        api_url = request.host_url.rstrip('/') + '/api/' + task.task_id
        sample_response = {
            'note': 'Total ' + str(len(sample_submissions)) + ' submission(s).',
            'submissions': sample_submissions,
            'task_id': task.task_id,
            'task_title': task.title,
            'total_submissions': len(sample_submissions)
        }
        sample_data_json = json.dumps(sample_response, ensure_ascii=False, indent=2)
        
        return render_template('smart_analyze.html', 
                             task=task, 
                             report=report,
                             preview_prompt=preview_prompt,
                             submission_count=submission_count,
                             has_api_key=has_api_key,
                             now=datetime.now(),
                             api_url=api_url,
                             sample_data_json=sample_data_json)
    finally:
        db.close()

@app.route('/download_report/<int:task_id>')
@login_required
def download_report(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).get(task_id)
        if not task:
            flash('任务不存在', 'danger')
            return redirect(url_for('dashboard'))
        if task.user_id != current_user.id:
            flash('无权访问此任务', 'danger')
            return redirect(url_for('dashboard'))

        report_file_path = task.report_file_path
        task_title = task.title
        report_content = task.analysis_report
        safe_title = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', task_title)
        safe_filename = f"{safe_title}_分析报告.html"

        if report_file_path and os.path.exists(report_file_path):
            return send_file(report_file_path, as_attachment=True, download_name=safe_filename, mimetype='text/html; charset=utf-8')

        if report_content and report_content.strip():
            report_time = task.report_generated_at.strftime('%Y-%m-%d %H:%M:%S') if task.report_generated_at else '未知'
            html_content = render_template('simple_report.html', task_title=task_title, report_time=report_time, report_content=report_content)
            return send_file(io.BytesIO(html_content.encode('utf-8')), as_attachment=True, download_name=safe_filename, mimetype='text/html; charset=utf-8')

        flash('该任务尚未生成分析报告，请先进行智能分析', 'info')
        return redirect(url_for('smart_analyze', task_id=task_id))

    except Exception as e:
        flash(f'下载报告时出错: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        db.close()

if __name__ == '__main__':
    # 修复socket.getfqdn()的UnicodeDecodeError问题
    import socket
    original_getfqdn = socket.getfqdn
    def safe_getfqdn(name=''):
        try:
            return original_getfqdn(name)
        except UnicodeDecodeError:
            return name if name else 'localhost'
    socket.getfqdn = safe_getfqdn
    
    # 启动应用
    app.run(debug=False, host='0.0.0.0', port=5001, threaded=True)