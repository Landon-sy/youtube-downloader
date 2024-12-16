import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import re
import m3u8
import subprocess
import time
import json

def sanitize_filename(filename):
    """处理文件名，移除非法字符"""
    illegal_chars = r'[<>:"/\\|?*]'
    filename = re.sub(illegal_chars, '_', filename)
    if len(filename) > 100:
        filename = filename[:100]
    return filename

def download_subtitle(subtitle_url, output_name, headers):
    """下载字幕文件"""
    try:
        print(f"\n开始下载字幕: {subtitle_url}")
        response = requests.get(subtitle_url, headers=headers)
        if response.status_code == 200:
            # 确定字幕文件扩展名
            ext = '.srt'
            if 'vtt' in subtitle_url.lower():
                ext = '.vtt'
            
            subtitle_path = f"{output_name}{ext}"
            with open(subtitle_path, 'wb') as f:
                f.write(response.content)
            print(f"字幕下载完成: {subtitle_path}")
            return True
    except Exception as e:
        print(f"下载��幕时出错: {str(e)}")
    return False

def find_subtitles(soup, url, headers):
    """查找页面中的字幕"""
    subtitles = []
    
    # 处理iframe
    for iframe in soup.find_all('iframe'):
        iframe_src = iframe.get('src')
        if iframe_src:
            if iframe_src.startswith('//'):
                iframe_src = 'https:' + iframe_src
            elif not iframe_src.startswith('http'):
                iframe_src = urljoin(url, iframe_src)
                
            try:
                # 获取iframe页面内容
                iframe_response = requests.get(iframe_src, headers=headers)
                iframe_soup = BeautifulSoup(iframe_response.text, 'html.parser')
                
                # 在iframe中查找字幕
                # 1. 查找track元素
                for track in iframe_soup.find_all('track'):
                    if track.get('src'):
                        subtitle_url = track.get('src')
                        if subtitle_url.startswith('//'):
                            subtitle_url = 'https:' + subtitle_url
                        elif not subtitle_url.startswith('http'):
                            subtitle_url = urljoin(iframe_src, subtitle_url)
                        subtitles.append({
                            'url': subtitle_url,
                            'label': track.get('label', 'Unknown'),
                            'language': track.get('srclang', 'Unknown')
                        })
                
                # 2. 查找script标签中的字幕信息
                for script in iframe_soup.find_all('script'):
                    if script.string and ('subtitle' in script.string.lower() or 'caption' in script.string.lower()):
                        # 尝试查找类似 subtitleUrl 或 captionFile 这样的变量
                        subtitle_patterns = [
                            r'subtitleUrl\s*=\s*[\'"]([^\'"]+)[\'"]',
                            r'captionFile\s*=\s*[\'"]([^\'"]+)[\'"]',
                            r'subtitle[^\'"]*[\'"]([^\'"]+\.(?:vtt|srt))[\'"]'
                        ]
                        for pattern in subtitle_patterns:
                            matches = re.findall(pattern, script.string)
                            for match in matches:
                                if match.startswith('//'):
                                    match = 'https:' + match
                                elif not match.startswith('http'):
                                    match = urljoin(iframe_src, match)
                                subtitles.append({
                                    'url': match,
                                    'label': 'Found in player',
                                    'language': 'Unknown'
                                })
                                
            except Exception as e:
                print(f"处理iframe时出错: {str(e)}")
    
    # 1. 查找video标签中的track元素
    for track in soup.find_all('track'):
        if track.get('src'):
            subtitle_url = track.get('src')
            if subtitle_url.startswith('//'):
                subtitle_url = 'https:' + subtitle_url
            elif not subtitle_url.startswith('http'):
                subtitle_url = urljoin(url, subtitle_url)
            subtitles.append({
                'url': subtitle_url,
                'label': track.get('label', 'Unknown'),
                'language': track.get('srclang', 'Unknown')
            })
    
    # 2. 在页面源码中查找.vtt或.srt文件
    subtitle_pattern = r'(https?://[^\s<>"]+?\.(?:vtt|srt)[^\s<>"]*)'
    subtitle_urls = re.findall(subtitle_pattern, str(soup))
    for sub_url in subtitle_urls:
        if sub_url not in [s['url'] for s in subtitles]:
            subtitles.append({
                'url': sub_url,
                'label': 'Found in page',
                'language': 'Unknown'
            })
    
    # 3. 查找可能包含字幕信息的script标签
    for script in soup.find_all('script'):
        script_text = script.string
        if script_text:
            if 'subtitle' in script_text.lower() or 'caption' in script_text.lower():
                try:
                    # 尝试解析JSON数据
                    data = json.loads(script_text)
                    # 这里需要根据具体网站结构调整字幕提取逻辑
                    # 这只是一个示例
                    if 'subtitles' in data:
                        for sub in data['subtitles']:
                            if 'url' in sub:
                                subtitles.append({
                                    'url': sub['url'],
                                    'label': sub.get('label', 'Unknown'),
                                    'language': sub.get('language', 'Unknown')
                                })
                except:
                    pass
    
    return subtitles

def download_m3u8(m3u8_url, output_name):
    """下载m3u8格式的视频"""
    try:
        print(f"\n开始处理m3u8视频: {m3u8_url}")
        
        if not os.path.exists('temp'):
            os.makedirs('temp')
            
        output_name = sanitize_filename(output_name)
        output_path = f"{output_name}.mp4"
        
        ffmpeg_path = r"C:\Users\Irisssy\Desktop\网页视频抓取\ffmpeg\bin\ffmpeg.exe"
        
        command = [
            ffmpeg_path,
            '-i', m3u8_url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            output_path
        ]
        
        print(f"\n开始下载视频到: {output_path}")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.communicate()
        
        if os.path.exists(output_path):
            print(f"\n视频下载完成: {output_path}")
            return True
        else:
            print("\n视频下载失败")
            return False
            
    except Exception as e:
        print(f"下载m3u8视频时出错: {str(e)}")
        return False
    finally:
        if os.path.exists('temp'):
            for file in os.listdir('temp'):
                os.remove(os.path.join('temp', file))
            os.rmdir('temp')

def extract_m3u8_url(url):
    """Extract m3u8 URL from a media URL or player URL"""
    try:
        # If it's already an m3u8 URL, return it directly
        if url.endswith('.m3u8'):
            return url
            
        # Handle URLs that start with //
        if url.startswith('//'):
            url = 'https:' + url
            
        # First check if there's an m3u8 URL in the query parameters
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        # Look for common parameter names that might contain the m3u8 URL
        for param in ['src', 'source', 'url', 'video']:
            if param in query_params:
                param_value = query_params[param][0]
                if '.m3u8' in param_value:
                    if param_value.startswith('//'):
                        return 'https:' + param_value
                    elif not param_value.startswith('http'):
                        return urljoin(url, param_value)
                    return param_value
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Try to fetch the URL content
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Look for m3u8 URLs in the response
        m3u8_pattern = r'(https?://[^\s<>"]+?\.m3u8[^\s<>"]*|//[^\s<>"]+?\.m3u8[^\s<>"]*)'
        m3u8_urls = re.findall(m3u8_pattern, response.text)
        
        if m3u8_urls:
            m3u8_url = m3u8_urls[0]
            if m3u8_url.startswith('//'):
                return 'https:' + m3u8_url
            return m3u8_url
            
        return None
        
    except Exception as e:
        print(f"提取m3u8 URL时出错: {str(e)}")
        return None

def download_media(url, save_path='.'):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        print("正在获取网页内容...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        print("正在解析网页...")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找字幕
        print("\n查找字幕文件...")
        subtitles = find_subtitles(soup, url, headers)
        if subtitles:
            print(f"\n找到 {len(subtitles)} 个字幕文件:")
            for sub in subtitles:
                print(f"- {sub['label']} ({sub['language']}): {sub['url']}")
        else:
            print("\n未找到字幕文件")
        
        # 查找视频源
        found_urls = set()
        
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if src:
                print(f"\n找到iframe: {src}")
                if 'm3u8' in src or 'video' in src or 'player' in src:
                    found_urls.add(src)
                    
        m3u8_pattern = r'(https?://[^\s<>"]+?\.m3u8[^\s<>"]*)'
        m3u8_urls = re.findall(m3u8_pattern, response.text)
        found_urls.update(m3u8_urls)
        
        for video in soup.find_all('video'):
            if video.get('src'):
                found_urls.add(video.get('src'))
            for source in video.find_all('source'):
                if source.get('src'):
                    found_urls.add(source.get('src'))
        
        if not found_urls:
            print("\n未找到媒体文件")
            return
            
        print("\n找到以下媒体链接：")
        for media_url in found_urls:
            print(f"\n{media_url}")
            
            m3u8_url = extract_m3u8_url(media_url)
            if m3u8_url:
                parsed_url = urlparse(media_url)
                query_params = parse_qs(parsed_url.query)
                video_title = query_params.get('t', ['video'])[0]
                video_title = sanitize_filename(video_title)
                
                print(f"\n正在下载视频: {video_title}")
                if download_m3u8(m3u8_url, video_title):
                    # 如果视频下载成功，尝试下载字幕
                    for subtitle in subtitles:
                        download_subtitle(subtitle['url'], video_title, headers)
            else:
                if media_url.startswith('//'):
                    media_url = 'https:' + media_url
                elif not media_url.startswith('http'):
                    media_url = urljoin(url, media_url)
                
                try:
                    print(f"\n尝试下载: {media_url}")
                    media_response = requests.get(media_url, headers=headers, stream=True)
                    if media_response.status_code == 200:
                        filename = os.path.join(save_path, sanitize_filename(media_url.split('/')[-1]))
                        with open(filename, 'wb') as f:
                            for chunk in media_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        print(f"下载完成: {filename}")
                        
                        # 下载相关字幕
                        for subtitle in subtitles:
                            download_subtitle(subtitle['url'], os.path.splitext(filename)[0], headers)
                    else:
                        print(f"无法下载，状态码: {media_response.status_code}")
                except Exception as e:
                    print(f"下载此链接时出错: {str(e)}")
            
    except Exception as e:
        print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    url = input("请输入网页URL: ")
    download_media(url)
