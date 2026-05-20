"""
试玩广告生成器 - 独立版本
无需 playable-editor 服务器，直接生成试玩广告包
"""
import sys
import os
import json
import zipfile
import io
import shutil
import subprocess
from pathlib import Path
import base64

# 修复 Windows 控制台中文编码问题
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def compress_video(video_path, max_size_bytes=2100*1024):
    """压缩视频到指定大小"""
    video_path = Path(video_path)
    if not video_path.exists():
        print(f"视频文件不存在: {video_path}")
        return None

    # 获取视频信息
    try:
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
    except:
        duration = 10  # 默认时长

    # 计算目标比特率
    target_bitrate_kbps = int((max_size_bytes * 8) / (duration * 1000))

    # 压缩视频
    output_path = video_path.parent / f"{video_path.stem}_compressed.mp4"

    # 使用 ffmpeg 压缩（如果可用）
    try:
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-b:v', f'{target_bitrate_kbps}k',
            '-y', str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"[压缩] {video_path.name}: {video_path.stat().st_size/1024:.0f}KB → {output_path.stat().st_size/1024:.0f}KB")
        return output_path
    except:
        # 如果 ffmpeg 不可用，直接返回原文件
        print(f"[警告] ffmpeg 不可用，使用原视频")
        return video_path


def video_to_base64(video_path):
    """将视频转换为 base64"""
    with open(video_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def generate_playable_html(config, platform='google'):
    """生成试玩广告 HTML"""

    # 读取视频并转换为 base64
    video_path = config['assets']['videoUrl']
    if video_path.startswith('/static/uploads/'):
        video_path = video_path.replace('/static/uploads/', '')

    video_base64 = video_to_base64(video_path)

    # 生成 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{config['appName']} - Playable Ad</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            overflow: hidden;
            width: 100vw;
            height: 100vh;
        }}
        #video-bg {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            z-index: -1;
        }}
        .chat-container {{
            position: absolute;
            top: {config['layout']['chatTop']}px;
            bottom: {config['layout']['chatBottom']}px;
            left: {config['layout']['chatPadding']}px;
            right: {config['layout']['chatPadding']}px;
            overflow-y: auto;
        }}
        .message {{
            margin-bottom: {config['layout']['messageSpacing']}px;
            display: flex;
            align-items: flex-end;
        }}
        .message.ai {{ justify-content: flex-start; }}
        .message.user {{ justify-content: flex-end; }}
        .bubble {{
            max-width: {config['layout']['bubbleMaxWidth']}%;
            padding: {config['layout']['bubblePadding']}px;
            border-radius: {config['layout']['bubbleBorderRadius']}px;
            font-size: {config['layout']['bubbleFontSize']}px;
            opacity: {config['layout']['bubbleOpacity']};
        }}
        .bubble.ai {{
            background: {config['theme']['aiBubbleBg']};
            color: white;
        }}
        .bubble.user {{
            background: {config['theme']['userBubbleGradient']};
            color: white;
        }}
        .input-area {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
        }}
        input {{
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 20px;
            background: rgba(255,255,255,0.9);
        }}
        button {{
            padding: 12px 24px;
            border: none;
            border-radius: 20px;
            background: {config['theme']['sendBtnGradient']};
            color: white;
            font-weight: bold;
            cursor: pointer;
        }}
        .endcard {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            display: none;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            color: white;
            text-align: center;
            padding: 40px;
        }}
        .endcard.show {{ display: flex; }}
        .endcard h1 {{ font-size: 32px; margin-bottom: 20px; }}
        .endcard p {{ font-size: 18px; margin-bottom: 40px; white-space: pre-line; }}
        .endcard button {{
            padding: 16px 48px;
            font-size: 20px;
        }}
    </style>
</head>
<body>
    <video id="video-bg" autoplay loop muted playsinline>
        <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
    </video>

    <div class="chat-container" id="chat"></div>

    <div class="input-area" id="input-area" style="display:none;">
        <input type="text" id="user-input" placeholder="输入消息...">
        <button onclick="sendMessage()">发送</button>
    </div>

    <div class="endcard" id="endcard">
        <h1>{config['endcard']['title']}</h1>
        <p>{config['endcard']['desc']}</p>
        <button onclick="downloadApp()">{config['endcard']['ctaText']}</button>
    </div>

    <script>
        const messages = {json.dumps(config['messages'])};
        const storeUrl = {json.dumps(config['storeUrl'])};
        let currentIndex = 0;

        function addMessage(type, content) {{
            const chat = document.getElementById('chat');
            const msg = document.createElement('div');
            msg.className = `message ${{type}}`;
            msg.innerHTML = `<div class="bubble ${{type}}">${{content}}</div>`;
            chat.appendChild(msg);
            chat.scrollTop = chat.scrollHeight;
        }}

        function showNextMessage() {{
            if (currentIndex >= messages.length) {{
                showEndcard();
                return;
            }}

            const msg = messages[currentIndex];
            currentIndex++;

            if (msg.type === 'ai') {{
                setTimeout(() => {{
                    addMessage('ai', msg.content);
                    showNextMessage();
                }}, msg.delayAfterPrev || 500);
            }} else if (msg.type === 'user_trigger') {{
                document.getElementById('input-area').style.display = 'flex';
            }} else if (msg.type === 'user_trigger_end') {{
                document.getElementById('input-area').style.display = 'flex';
            }}
        }}

        function sendMessage() {{
            const input = document.getElementById('user-input');
            if (input.value.trim()) {{
                addMessage('user', input.value);
                input.value = '';
                document.getElementById('input-area').style.display = 'none';
                showNextMessage();
            }}
        }}

        function showEndcard() {{
            document.getElementById('endcard').classList.add('show');
        }}

        function downloadApp() {{
            const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
            const url = isIOS ? storeUrl.ios : storeUrl.android;
            window.open(url, '_blank');
        }}

        // 开始播放
        setTimeout(() => showNextMessage(), 1000);
    </script>
</body>
</html>"""

    return html


def main():
    print("试玩广告生成器 v1.0.0")
    print("=" * 50)

    # 这里可以添加命令行参数解析
    # 或者直接调用生成函数

    print("请使用 batch_export.py 进行批量生成")


if __name__ == "__main__":
    main()
