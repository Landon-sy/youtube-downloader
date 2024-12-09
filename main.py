from fastapi import FastAPI, Request, BackgroundTasks, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import yt_dlp
import os
from pathlib import Path
import time
import hashlib
import json

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# 修改文件存储路径
DOWNLOAD_DIR = Path("/tmp")  # Vercel 只允许写入 /tmp 目录
DOWNLOAD_DIR.mkdir(exist_ok=True)

# 存储下载任务状态
download_tasks = {}

# 生成唯一的任务ID
def generate_task_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

# 下载进度回调
def progress_hook(d):
    global current_task_id  # 使用全局变量存储当前任务ID
    
    if d['status'] == 'downloading':
        try:
            # 获取下载百分比
            if '_percent_str' in d:
                percent = d['_percent_str'].replace('%', '')
            else:
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                percent = '0'
                if total > 0:
                    percent = f"{(downloaded / total) * 100:.1f}"

            speed = d.get('speed_str', '--') or d.get('_speed_str', '--')
            eta = d.get('eta_str', '--') or d.get('_eta_str', '--')
            
            print(f"Task ID: {current_task_id}, Progress: {percent}%, Speed: {speed}, ETA: {eta}")
            
            download_tasks[current_task_id] = {
                'status': 'downloading',
                'progress': f"{percent}%",
                'speed': speed,
                'eta': eta
            }
        except Exception as e:
            print(f"Error in progress_hook: {str(e)}")
            
    elif d['status'] == 'finished':
        print(f"Download finished for task: {current_task_id}")
        download_tasks[current_task_id] = {
            'status': 'finished',
            'progress': '100%'
        }

# 下载视频函数
def download_video(url: str, task_id: str):
    global current_task_id
    current_task_id = task_id
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': str(DOWNLOAD_DIR / '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'quiet': False,
        'no_warnings': False,
        'merge_output_format': 'mp4',
        'keepvideo': True,
        'writethumbnail': False,
        'verbose': True,
        # 添加文件大小限制
        'max_filesize': 50 * 1024 * 1024  # 50MB 限制
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return {
                'title': info['title'],
                'duration': info['duration'],
                'uploader': info['uploader'],
                'description': info['description'],
                'filename': info['requested_downloads'][0]['filename'],
                'filesize': info['requested_downloads'][0]['filesize']
            }
    except Exception as e:
        print(f"Download error for task {task_id}: {str(e)}")
        download_tasks[task_id] = {
            'status': 'error',
            'error': str(e)
        }
        return {'error': str(e)}

@app.get("/")
async def home(request: Request):
    # 获取已下载视频列表
    videos = []
    for file in DOWNLOAD_DIR.glob("*"):
        if file.is_file():
            videos.append({
                'filename': file.name,
                'path': f"/downloads/{file.name}",
                'size': f"{file.stat().st_size / (1024*1024):.1f} MB"
            })
    
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "videos": videos}
    )

@app.post("/download")
async def start_download(background_tasks: BackgroundTasks, url: str = Form(...)):
    task_id = generate_task_id(url)
    print(f"Created new download task: {task_id} for URL: {url}")
    
    # 初始化任务状态
    download_tasks[task_id] = {
        "status": "pending",
        "progress": "0%",
        "speed": "--",
        "eta": "--"
    }
    
    # 启动下载任务
    background_tasks.add_task(download_video, url, task_id)
    return {"task_id": task_id}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    status = download_tasks.get(task_id, {
        "status": "pending",
        "progress": "0%",
        "speed": "--",
        "eta": "--"
    })
    print(f"Status request for {task_id}: {status}")
    return status

# 配置视频文件访问
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

# 添加健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# 在 FastAPI 应用启动时添加错误处理
@app.exception_handler(500)
async def internal_server_error(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "message": "Internal server error",
            "detail": str(exc)
        }
    )