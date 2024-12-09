from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import yt_dlp

# 修改为使用 /tmp 目录（Vercel 允许写入的唯一目录）
DOWNLOAD_DIR = Path("/tmp/downloads")

# 初始化 FastAPI 应用
app = FastAPI()

# 设置模板目录
templates = Jinja2Templates(directory="templates")

# 在应用启动时创建临时目录
@app.on_event("startup")
async def startup_event():
    os.makedirs("/tmp/downloads", exist_ok=True)

# 修改静态文件挂载
app.mount("/downloads", StaticFiles(directory="/tmp/downloads"), name="downloads")

# 主页路由
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 下载视频路由
@app.post("/download")
async def download_video(url: str = Form(...)):
    try:
        # 设置下载选项
        ydl_opts = {
            'format': 'best',  # 下载最佳质量
            'outtmpl': str(DOWNLOAD_DIR / '%(title)s.%(ext)s'),  # 输出模板
        }
        
        # 使用 yt-dlp 下载视频
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info['title']
            video_ext = info['ext']
            filename = f"{video_title}.{video_ext}"
            
        # 返回成功信息
        return {
            "status": "success",
            "message": "Video downloaded successfully",
            "filename": filename,
            "download_path": f"/downloads/{filename}"
        }
        
    except Exception as e:
        # 返回错误信息
        return {
            "status": "error",
            "message": str(e)
        }

# 错误处理
@app.exception_handler(500)
async def internal_server_error(request: Request, exc: Exception):
    return {
        "status": "error",
        "message": "Internal server error",
        "detail": str(exc)
    }
