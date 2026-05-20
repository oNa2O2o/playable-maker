"""试玩广告实时编辑器 — Flask 后端"""
import os
import io
import re
import sys
import json
import base64
import zipfile
import shutil
import datetime
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# 版本号 — 每次发布递增
APP_VERSION = '1.2.7'

# GitHub 仓库信息（如需自动更新功能，请配置环境变量）
GITHUB_REPO = os.getenv('GITHUB_REPO', '')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / 'static' / 'uploads'
OUTPUT_DIR = BASE_DIR / 'output'
CONFIGS_DIR = BASE_DIR / 'configs'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CONFIGS_DIR.mkdir(parents=True, exist_ok=True)


# ---------- 页面路由 ----------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/preview')
def preview():
    return render_template('preview.html')


# ---------- 资源上传 ----------

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'error': '文件名为空'}), 400
    # 安全文件名
    safe_name = re.sub(r'[^\w.\-]', '_', f.filename)
    save_path = UPLOAD_DIR / safe_name
    f.save(str(save_path))
    return jsonify({'url': f'/static/uploads/{safe_name}', 'filename': safe_name})


# ---------- 配置管理 ----------

@app.route('/api/configs', methods=['GET'])
def list_configs():
    """列出所有保存的配置"""
    configs = []
    for f in sorted(CONFIGS_DIR.glob('*.json')):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            configs.append({
                'name': f.stem,
                'appName': data.get('appName', ''),
                'aiName': data.get('aiName', ''),
                'messageCount': len(data.get('messages', [])),
                'filename': f.name
            })
        except Exception:
            pass
    return jsonify({'configs': configs})


@app.route('/api/configs/<name>', methods=['GET'])
def get_config(name):
    """获取指定配置"""
    safe_name = re.sub(r'[^\w.\-]', '_', name)
    path = CONFIGS_DIR / f'{safe_name}.json'
    if not path.exists():
        return jsonify({'error': '配置不存在'}), 404
    data = json.loads(path.read_text(encoding='utf-8'))
    return jsonify({'config': data, 'name': safe_name})


@app.route('/api/configs/<name>', methods=['PUT'])
def save_config(name):
    """保存配置"""
    safe_name = re.sub(r'[^\w.\-]', '_', name)
    if not safe_name:
        return jsonify({'error': '无效的配置名'}), 400
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的配置数据'}), 400
    path = CONFIGS_DIR / f'{safe_name}.json'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return jsonify({'ok': True, 'name': safe_name})


@app.route('/api/configs/<name>', methods=['DELETE'])
def delete_config(name):
    """删除配置"""
    safe_name = re.sub(r'[^\w.\-]', '_', name)
    path = CONFIGS_DIR / f'{safe_name}.json'
    if path.exists():
        path.unlink()
    return jsonify({'ok': True})


# ---------- 视频压缩 ----------

def _get_ffmpeg():
    """获取 ffmpeg 可执行文件路径"""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


COMPRESSED_DIR = BASE_DIR / 'static' / 'uploads' / 'compressed'
COMPRESSED_DIR.mkdir(parents=True, exist_ok=True)


def compress_video(input_path: str, max_size_bytes: int = 2100 * 1024) -> str:
    """
    将视频压缩到 max_size_bytes 以内，返回压缩后文件路径。
    默认目标 2100KB — 经 base64 编码(×1.33)后约 2800KB，
    加上 HTML 代码约 36KB，ZIP 压缩后约 1.9MB，
    符合各平台 < 2MB（TikTok/Google 5MB）要求。
    """
    input_path = Path(input_path)
    if not input_path.exists():
        return str(input_path)

    file_size = input_path.stat().st_size
    if file_size <= max_size_bytes:
        return str(input_path)

    ffmpeg = _get_ffmpeg()
    if not ffmpeg:
        print('[警告] ffmpeg 不可用，跳过视频压缩')
        return str(input_path)

    out_name = input_path.stem + '_compressed' + input_path.suffix
    out_path = COMPRESSED_DIR / out_name

    # 如果压缩版已存在且在目标范围内且比源文件新，直接复用
    if out_path.exists() and out_path.stat().st_mtime >= input_path.stat().st_mtime:
        sz = out_path.stat().st_size
        if sz <= max_size_bytes:
            return str(out_path)

    # 获取视频时长
    probe_cmd = [ffmpeg, '-i', str(input_path), '-hide_banner']
    probe = subprocess.run(probe_cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
    duration = 10.0
    for line in probe.stderr.split('\n'):
        if 'Duration:' in line:
            import re as _re
            m = _re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)', line)
            if m:
                duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            break

    # 目标码率，留 5% 余量
    target_bitrate = int((max_size_bytes * 8 * 0.95) / duration / 1000)
    target_bitrate = max(target_bitrate, 300)

    # 保持原始分辨率（不缩放），尽量保持画质
    cmd = [
        ffmpeg, '-y', '-i', str(input_path),
        '-c:v', 'libx264',
        '-b:v', f'{target_bitrate}k',
        '-maxrate', f'{int(target_bitrate * 1.2)}k',
        '-bufsize', f'{int(target_bitrate * 2)}k',
        '-preset', 'slow',
        '-profile:v', 'high',
        '-pix_fmt', 'yuv420p',
        '-an',
        '-movflags', '+faststart',
        str(out_path)
    ]

    print(f'[压缩] {input_path.name}: {file_size/1024:.0f}KB → 目标 {target_bitrate}kbps, 时长 {duration:.1f}s')
    subprocess.run(cmd, capture_output=True, text=True,
                   encoding='utf-8', errors='replace')

    if out_path.exists():
        new_size = out_path.stat().st_size
        print(f'[压缩] 完成: {new_size/1024:.0f}KB ({new_size/file_size*100:.0f}%)')
        # 如果还是太大，用稍低码率重试
        if new_size > max_size_bytes:
            target_bitrate_2 = int(target_bitrate * max_size_bytes / new_size * 0.95)
            target_bitrate_2 = max(target_bitrate_2, 200)
            cmd[cmd.index(f'{target_bitrate}k')] = f'{target_bitrate_2}k'
            cmd[cmd.index(f'{int(target_bitrate * 1.2)}k')] = f'{int(target_bitrate_2 * 1.2)}k'
            cmd[cmd.index(f'{int(target_bitrate * 2)}k')] = f'{int(target_bitrate_2 * 2)}k'
            print(f'[压缩] 二次: 目标 {target_bitrate_2}kbps')
            subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
            if out_path.exists():
                print(f'[压缩] 二次完成: {out_path.stat().st_size/1024:.0f}KB')

    return str(out_path) if out_path.exists() else str(input_path)


# ---------- 资源转 Base64 ----------

def url_to_base64(url: str) -> str:
    """下载远程资源并转为 data URI"""
    if not url:
        return ''
    # 已经是 data URI
    if url.startswith('data:'):
        return url
    # 本地文件
    if url.startswith('/static/'):
        local_path = BASE_DIR / url.lstrip('/')
        if local_path.exists():
            data = local_path.read_bytes()
            mime = _guess_mime(str(local_path))
            return f'data:{mime};base64,{base64.b64encode(data).decode()}'
    # 远程 URL — 增加重试
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                content_type = resp.headers.get('Content-Type', 'application/octet-stream')
                mime = content_type.split(';')[0].strip()
                return f'data:{mime};base64,{base64.b64encode(data).decode()}'
        except Exception as e:
            print(f'[警告] 下载资源失败 (第{attempt+1}次) {url}: {e}')
    return ''  # 不回退为原始 URL


def _guess_mime(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml',
        '.mp4': 'video/mp4', '.webm': 'video/webm',
    }.get(ext, 'application/octet-stream')


# ---------- 本地化翻译 ----------

LOCALE_NAMES = {
    'JP': '日本語（日本語に翻訳してください）',
    'EN': 'English (translate to English)',
    'TC': '繁體中文（翻譯為繁體中文）',
}

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')


def localize_content(messages: list, endcard: dict, locale: str) -> tuple:
    """调用 OpenRouter API 翻译消息内容和结束页文案"""
    locale_desc = LOCALE_NAMES.get(locale, locale)

    # 收集需要翻译的文本
    texts_to_translate = []
    for msg in messages:
        if msg.get('type') == 'ai' and msg.get('content'):
            texts_to_translate.append(msg['content'])

    endcard_title = endcard.get('title', '')
    endcard_desc = endcard.get('desc', '')
    endcard_cta = endcard.get('ctaText', '')
    if endcard_title:
        texts_to_translate.append(endcard_title)
    if endcard_desc:
        texts_to_translate.append(endcard_desc)
    if endcard_cta:
        texts_to_translate.append(endcard_cta)

    if not texts_to_translate:
        return messages, endcard

    # 构建 prompt
    numbered = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(texts_to_translate))
    prompt = f"""Translate the following texts to {locale_desc}. Keep the same format and numbering. Only output the translations, one per line with the same numbering. Do not add explanations.

{numbered}"""

    try:
        req_data = json.dumps({
            'model': 'google/gemini-3-flash',
            'messages': [{'role': 'user', 'content': prompt}]
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://openrouter.ai/api/v1/chat/completions',
            data=req_data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'User-Agent': 'PlayableEditor/1.0'
            }
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        reply = result['choices'][0]['message']['content'].strip()
        # 解析翻译结果
        lines = [l.strip() for l in reply.split('\n') if l.strip()]
        translated = []
        for line in lines:
            # 移除开头的编号 "1. " "2. " 等
            cleaned = re.sub(r'^\d+\.\s*', '', line)
            translated.append(cleaned)

        # 映射回原位置
        idx = 0
        new_messages = json.loads(json.dumps(messages))
        for msg in new_messages:
            if msg.get('type') == 'ai' and msg.get('content'):
                if idx < len(translated):
                    msg['content'] = translated[idx]
                idx += 1

        new_endcard = dict(endcard)
        if endcard_title and idx < len(translated):
            new_endcard['title'] = translated[idx]
            idx += 1
        if endcard_desc and idx < len(translated):
            new_endcard['desc'] = translated[idx]
            idx += 1
        if endcard_cta and idx < len(translated):
            new_endcard['ctaText'] = translated[idx]
            idx += 1

        return new_messages, new_endcard
    except Exception as e:
        print(f'[警告] 翻译失败 ({locale}): {e}')
        return messages, endcard


@app.route('/api/localize', methods=['POST'])
def api_localize():
    """翻译消息和结束页文案"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求'}), 400

    messages = data.get('messages', [])
    locale = data.get('locale', 'EN')
    endcard = data.get('endcard', {})

    new_messages, new_endcard = localize_content(messages, endcard, locale)
    return jsonify({'messages': new_messages, 'endcard': new_endcard})


# ---------- 生成试玩广告 HTML ----------

# UI 本地化字符串
UI_STRINGS = {
    'EN': {
        'lang': 'en',
        'placeholder': 'Type a message...',
        'space': 'space',
        'send': 'Send',
        'typing': 'Typing...',
        'read': 'Read',
        'you': 'You',
        'hint': 'Tap anywhere to continue ↓',
        'rotate': 'Please rotate to portrait mode',
    },
    'JP': {
        'lang': 'ja',
        'placeholder': 'メッセージを入力...',
        'space': 'スペース',
        'send': '送信',
        'typing': '入力中...',
        'read': '既読',
        'you': 'あなた',
        'hint': 'タップして続ける ↓',
        'rotate': '縦画面にしてください',
    },
    'TC': {
        'lang': 'zh-Hant',
        'placeholder': '輸入訊息...',
        'space': '空格',
        'send': '發送',
        'typing': '輸入中...',
        'read': '已讀',
        'you': '你',
        'hint': '點擊任意位置繼續 ↓',
        'rotate': '請旋轉至豎屏模式',
    },
    'CN': {
        'lang': 'zh-CN',
        'placeholder': '输入消息...',
        'space': '空格',
        'send': '发送',
        'typing': '输入中...',
        'read': '已读',
        'you': '你',
        'hint': '点击任意位置继续 ↓',
        'rotate': '请旋转至竖屏模式',
    },
}


def _generate_bgm_js(style: str = 'ambient') -> str:
    """生成 Web Audio API 背景音乐 JS 代码（不同风格）"""
    # 和弦进行配置
    chord_configs = {
        'ambient': {
            'chords': [[261.63,329.63,392],[349.23,440,523.25],[293.66,369.99,440],[261.63,329.63,392]],
            'dur': 4, 'vol': 0.12, 'freq_mult': 0.5, 'filter': 800,
            'sparkle_notes': [523.25,659.25,783.99,880,1046.5], 'sparkle_vol': 0.15,
        },
        'dreamy': {
            'chords': [[261.63,329.63,392],[220,277.18,329.63],[293.66,349.23,440],[261.63,329.63,392]],
            'dur': 5, 'vol': 0.10, 'freq_mult': 0.25, 'filter': 600,
            'sparkle_notes': [659.25,783.99,987.77,1174.66], 'sparkle_vol': 0.12,
        },
        'upbeat': {
            'chords': [[329.63,415.30,493.88],[349.23,440,523.25],[392,493.88,587.33],[329.63,415.30,493.88]],
            'dur': 3, 'vol': 0.14, 'freq_mult': 0.5, 'filter': 1000,
            'sparkle_notes': [587.33,698.46,880,1046.5,1174.66], 'sparkle_vol': 0.18,
        },
    }
    cfg = chord_configs.get(style, chord_configs['ambient'])
    chords_json = json.dumps(cfg['chords'])

    return f'''// === BGM: Web Audio API 背景音乐 ===
var bgmCtx=null,bgmStarted=false,bgmMaster=null;
function initBGM(){{
  if(bgmCtx)return;
  try{{
    bgmCtx=new(window.AudioContext||window.webkitAudioContext)();
    bgmMaster=bgmCtx.createGain();bgmMaster.gain.value={cfg['vol']};bgmMaster.connect(bgmCtx.destination);
    bgmCtx.onstatechange=function(){{if(bgmCtx.state==='running')playBGM()}};
  }}catch(e){{}}
}}
function playBGM(){{
  if(bgmStarted||!bgmCtx||!bgmMaster||bgmCtx.state!=='running')return;
  bgmStarted=true;
  var chords={chords_json};
  var chordDur={cfg['dur']},totalDur=chords.length*chordDur;
  function playChordLoop(){{
    if(!bgmCtx)return;
    var now=bgmCtx.currentTime;
    for(var c=0;c<chords.length;c++){{
      var notes=chords[c];
      for(var n=0;n<notes.length;n++){{
        var osc=bgmCtx.createOscillator();
        var g=bgmCtx.createGain();
        var f=bgmCtx.createBiquadFilter();
        f.type='lowpass';f.frequency.value={cfg['filter']};
        osc.type='sine';osc.frequency.value=notes[n]*{cfg['freq_mult']};
        osc.connect(f);f.connect(g);g.connect(bgmMaster);
        var t=now+c*chordDur;
        g.gain.setValueAtTime(0,t);
        g.gain.linearRampToValueAtTime(0.3,t+0.8);
        g.gain.setValueAtTime(0.3,t+chordDur-1);
        g.gain.linearRampToValueAtTime(0,t+chordDur);
        osc.start(t);osc.stop(t+chordDur);
      }}
    }}
    setTimeout(playChordLoop,totalDur*1000-200);
  }}
  function playSparkle(){{
    if(!bgmCtx)return;
    var sparkleNotes={json.dumps(cfg['sparkle_notes'])};
    var now=bgmCtx.currentTime;
    var note=sparkleNotes[Math.floor(Math.random()*sparkleNotes.length)];
    var osc=bgmCtx.createOscillator();
    var g=bgmCtx.createGain();
    var f=bgmCtx.createBiquadFilter();
    f.type='lowpass';f.frequency.value=1200;
    osc.type='triangle';osc.frequency.value=note;
    osc.connect(f);f.connect(g);g.connect(bgmMaster);
    g.gain.setValueAtTime(0,now);
    g.gain.linearRampToValueAtTime({cfg['sparkle_vol']},now+0.1);
    g.gain.exponentialRampToValueAtTime(0.001,now+2.5);
    osc.start(now);osc.stop(now+2.5);
    setTimeout(playSparkle,2000+Math.random()*4000);
  }}
  playChordLoop();
  setTimeout(playSparkle,1000);
}}
function startBGM(){{
  initBGM();
  if(bgmCtx&&bgmCtx.state==='suspended')bgmCtx.resume();
  playBGM();
}}
startBGM();
var _bgmEvts=['touchstart','touchend','mousedown','click','keydown','pointerdown'];
function _bgmResume(){{
  startBGM();
  if(bgmStarted)_bgmEvts.forEach(function(e){{document.removeEventListener(e,_bgmResume,true)}});
}}
_bgmEvts.forEach(function(e){{document.addEventListener(e,_bgmResume,true)}});
'''


def generate_playable_html(config: dict, platform: str, locale: str = '') -> str:
    """根据配置和平台生成自包含 HTML"""
    messages = config.get('messages', [])
    app_name = config.get('appName', 'MiraiMind')
    ai_name = config.get('aiName', 'Eric')
    store_url = config.get('storeUrl', {})
    android_url = store_url.get('android', '')
    ios_url = store_url.get('ios', '')
    theme = config.get('theme', {})
    timing = config.get('timing', {})
    endcard = config.get('endcard', {})
    assets = config.get('assets', {})

    layout = config.get('layout', {})

    # UI 语言：优先用导出时指定的 locale，其次用 config 中的 locale
    ui_locale = locale or config.get('locale', 'EN')
    ui = UI_STRINGS.get(ui_locale, UI_STRINGS['EN'])

    # Logo 始终 base64 内嵌
    logo_data = url_to_base64(assets.get('logoUrl', ''))

    # 视频处理：所有平台都压缩后 base64 内嵌
    video_url = assets.get('videoUrl', '')
    video_data = ''
    video_file_path = None

    if video_url:
        if video_url.startswith('/static/'):
            local_video = BASE_DIR / video_url.lstrip('/')
            if local_video.exists():
                compressed_path = compress_video(str(local_video))
                compressed_rel = '/static/' + str(Path(compressed_path).relative_to(BASE_DIR / 'static')).replace('\\', '/')
                video_data = url_to_base64(compressed_rel)
            else:
                video_data = url_to_base64(video_url)
        else:
            video_data = url_to_base64(video_url)

    # 平台特定的 CTA 方法
    if platform == 'tiktok':
        cta_js = "if(typeof window.openAppStore==='function'){window.openAppStore();return;}"
    elif platform == 'google':
        cta_js = "if(typeof window.ExitApi!=='undefined'&&typeof window.ExitApi.exit==='function'){window.ExitApi.exit();return;}"
    elif platform == 'facebook':
        cta_js = "if(typeof window.FbPlayableAd!=='undefined'&&typeof window.FbPlayableAd.onCTAClick==='function'){window.FbPlayableAd.onCTAClick();return;}"
    else:
        cta_js = ""

    # fallback：Facebook 禁止任何 JS 重定向，其他平台可以用 location.href 兜底
    if platform == 'facebook':
        cta_fallback = ""
    else:
        cta_fallback = f"""
        var ua=navigator.userAgent||'';
        var url=/iPad|iPhone|iPod/.test(ua)?'{ios_url}':'{android_url}';
        window.location.href=url;
    """

    # Google 平台特有的 meta（同时支持横竖屏）
    google_meta = '<meta name="ad.orientation" content="portrait,landscape">' if platform == 'google' else ''

    # 平台特有的 head 脚本
    if platform == 'google':
        platform_head_script = '<script type="text/javascript" src="https://tpc.googlesyndication.com/pagead/gadgets/html5/api/exitapi.js"></script>'
    else:
        platform_head_script = ''

    # TikTok 要求 HTML 中必须包含 Pangle js-sdk 脚本标签（上传时静态检测）
    # TikTok 环境会拦截并注入 SDK，本地测试时脚本超时后 fallback 仍可用
    if platform == 'tiktok':
        platform_body_script = '<script src="https://sf16-muse-va.ibytedtos.com/obj/union-fe-nc-i18n/playable/sdk/playable-sdk.js"></script>'
    else:
        platform_body_script = ''

    # 视频标签的 src 属性
    video_src_attr = f'src="{video_data}"' if video_data else ''

    # 构建消息数据 JSON
    messages_json = json.dumps(messages, ensure_ascii=False)

    # 结束页描述换行处理
    end_desc_html = endcard.get('desc', '').replace('\n', '<br>')

    send_btn_gradient = theme.get('sendBtnGradient', 'linear-gradient(135deg, #F472B6, #60A5FA, #4ADE80, #FBBF24)')
    ai_bubble_bg = theme.get('aiBubbleBg', 'linear-gradient(135deg, rgba(0,0,0,0.7), rgba(0,0,0,0.6))')
    user_bubble_gradient = theme.get('userBubbleGradient', 'linear-gradient(135deg, #4ADE80, #60A5FA)')
    bg_overlay = theme.get('bgOverlay', 'rgba(0,0,0,0.4)')
    typing_duration = timing.get('typingDuration', 500)
    message_gap = timing.get('messageGap', 200)
    auto_end_delay = timing.get('autoEndDelay', 2000)

    # BGM 参数
    bgm = config.get('bgm', {})
    bgm_enabled = bgm.get('enabled', False)
    bgm_style = bgm.get('style', 'ambient')  # ambient / upbeat / dreamy

    # 布局参数
    ly_header_top = layout.get('headerTop', 50)
    ly_chat_top = layout.get('chatTop', 110)
    ly_chat_bottom = layout.get('chatBottom', 280)
    ly_chat_padding = layout.get('chatPadding', 20)
    ly_bubble_max_w = layout.get('bubbleMaxWidth', 75)
    ly_bubble_padding = layout.get('bubblePadding', 12)
    ly_bubble_radius = layout.get('bubbleBorderRadius', 18)
    ly_bubble_font = layout.get('bubbleFontSize', 14)
    ly_bubble_opacity = layout.get('bubbleOpacity', 1.0)
    ly_msg_spacing = layout.get('messageSpacing', 16)
    ly_sender_font = layout.get('senderFontSize', 12)
    ly_avatar_size = layout.get('avatarSize', 44)

    html = f'''<!DOCTYPE html>
<html lang="{ui['lang']}" style="overflow:hidden;">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
{google_meta}
{platform_head_script}
<title>{app_name} - AI Chat</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}}
body{{margin:0;overflow:hidden;background:#000;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;width:100vw;height:100vh;display:flex;justify-content:center;align-items:center}}
.root{{position:relative;width:100%;height:100vh;background:#000;overflow:hidden}}
.video-bg{{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;z-index:1}}
.gradient-overlay{{position:absolute;top:0;left:0;width:100%;height:100%;background:linear-gradient(to bottom,rgba(0,0,0,0.3) 0%,rgba(0,0,0,0.1) 30%,rgba(0,0,0,0.2) 70%,rgba(0,0,0,0.6) 100%);z-index:2;pointer-events:none}}
.page{{position:absolute;top:0;left:0;width:100%;height:100%;z-index:10;opacity:0;pointer-events:none;transition:opacity 0.5s ease}}
.page.active{{opacity:1;pointer-events:auto}}
.page2{{display:flex;flex-direction:column}}
.chat-header{{position:absolute;top:6vh;left:0;right:0;display:flex;align-items:center;justify-content:center;gap:min(12px,2vw);z-index:20}}
.header-avatar{{width:min({ly_avatar_size}px,10vw);height:min({ly_avatar_size}px,10vw);border-radius:12px;object-fit:cover}}
.header-name{{font-size:min(18px,4vw);font-weight:700;color:#fff;text-shadow:0 2px 4px rgba(0,0,0,0.8),0 0 20px rgba(0,0,0,0.5)}}
.chat-container{{position:absolute;top:14vh;left:0;right:0;bottom:38vh;overflow-y:auto;padding:{ly_chat_padding}px;z-index:10;display:flex;flex-direction:column;scrollbar-width:none;-ms-overflow-style:none}}
.chat-container::-webkit-scrollbar{{display:none}}
.chat-message{{display:flex;flex-direction:column;margin-bottom:{ly_msg_spacing}px;opacity:0;transform:translateY(20px);transition:all 0.3s ease;max-width:{ly_bubble_max_w}%}}
.chat-message.show{{opacity:1;transform:translateY(0)}}
.chat-message.ai{{align-self:flex-start;align-items:flex-start}}
.chat-message.user{{align-self:flex-end;align-items:flex-end}}
.message-sender{{font-size:{ly_sender_font}px;color:#fff;margin-bottom:4px;font-weight:500;text-shadow:0 1px 3px rgba(0,0,0,0.9),0 0 10px rgba(0,0,0,0.8)}}
.message-content{{padding:{ly_bubble_padding}px {ly_bubble_padding + 4}px;border-radius:{ly_bubble_radius}px;font-size:{ly_bubble_font}px;line-height:1.4;word-wrap:break-word;text-shadow:0 1px 3px rgba(0,0,0,0.9),0 2px 6px rgba(0,0,0,0.8);opacity:{ly_bubble_opacity}}}
.chat-message.ai .message-content{{background:{ai_bubble_bg};border:1px solid rgba(255,255,255,0.3);color:#fff;border-bottom-left-radius:4px}}
.chat-message.user .message-content{{background:{user_bubble_gradient};color:#fff;border-bottom-right-radius:4px}}
.message-meta{{font-size:10px;color:#fff;margin-top:4px;display:flex;align-items:center;gap:6px;text-shadow:0 1px 3px rgba(0,0,0,0.9),0 0 8px rgba(0,0,0,0.8)}}
.message-status{{color:#4ADE80;font-weight:500}}
.input-area{{position:absolute;bottom:0;left:0;right:0;background:{bg_overlay};backdrop-filter:blur(20px);padding:1vh 3vw 2vh;z-index:30}}
.input-box{{display:flex;align-items:center;background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);border-radius:25px;padding:1vh 3vw;margin-bottom:1vh}}
.input-field{{flex:1;background:transparent;border:none;color:#fff;font-size:min(15px,3.5vw);outline:none;padding:0.5vh 1vw}}
.input-field::placeholder{{color:rgba(255,255,255,0.4)}}
.send-btn{{width:min(36px,8vw);height:min(36px,8vw);background:{send_btn_gradient};background-size:200% 200%;animation:gs 3s ease infinite;border:none;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:transform 0.2s;box-shadow:0 2px 8px rgba(244,114,182,0.4)}}
@keyframes gs{{0%{{background-position:0% 50%}}50%{{background-position:100% 50%}}100%{{background-position:0% 50%}}}}
.send-btn:active{{transform:scale(0.9)}}
.send-btn svg{{width:18px;height:18px;fill:white}}
.virtual-keyboard{{padding:0.5vh 1vw;background:rgba(0,0,0,0.3);border-radius:12px;backdrop-filter:blur(10px)}}
.keyboard-row{{display:flex;justify-content:center;margin-bottom:min(6px,1vh);gap:min(4px,1vw)}}
.key{{min-width:0;height:min(38px,5vh);background:rgba(255,255,255,0.15);border:none;border-radius:6px;color:#fff;font-size:min(15px,3vw);font-weight:500;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.1s;user-select:none;flex:1}}
.key:active,.key.pressed{{background:linear-gradient(135deg,#F472B6,#60A5FA);transform:scale(0.95)}}
.key.wide{{flex:1.3}}
.key.space{{flex:3}}
.key.send{{background:{send_btn_gradient};background-size:200% 200%;animation:gs 3s ease infinite;flex:1.5;font-weight:600}}
.typing-indicator{{display:flex;gap:4px;padding:12px 16px;background:linear-gradient(135deg,rgba(244,114,182,0.25),rgba(96,165,250,0.25));border:1px solid rgba(255,255,255,0.2);border-radius:18px;border-bottom-left-radius:4px;width:fit-content}}
.typing-dot{{width:8px;height:8px;background:rgba(255,255,255,0.6);border-radius:50%;animation:tp 0.5s infinite}}
.typing-dot:nth-child(2){{animation-delay:0.07s}}
.typing-dot:nth-child(3){{animation-delay:0.14s}}
@keyframes tp{{0%,100%{{opacity:1}}50%{{opacity:0.5}}}}
.typing-text{{color:#fff;font-size:14px;font-style:italic;margin-left:4px}}
@keyframes fiu{{from{{opacity:0;transform:translateY(30px)}}to{{opacity:1;transform:translateY(0)}}}}
.end-page{{position:absolute;top:0;left:0;width:100%;height:100%;z-index:100;opacity:0;pointer-events:none;transition:opacity 0.5s ease;display:flex;flex-direction:column;align-items:center;justify-content:center;background:rgba(0,0,0,0.7);backdrop-filter:blur(10px)}}
.end-page.active{{opacity:1;pointer-events:auto}}
.end-content{{text-align:center;animation:fiu 0.6s ease}}
.end-logo{{width:100px;height:100px;border-radius:24px;margin-bottom:20px;box-shadow:0 10px 40px rgba(0,0,0,0.5)}}
.end-title{{font-size:28px;font-weight:700;color:#fff;margin-bottom:10px;text-shadow:0 2px 8px rgba(0,0,0,0.9),0 0 20px rgba(0,0,0,0.8)}}
.end-desc{{font-size:16px;color:#fff;margin-bottom:30px;line-height:1.6;text-shadow:0 1px 4px rgba(0,0,0,0.9),0 0 12px rgba(0,0,0,0.8)}}
.download-section{{display:flex;align-items:center;justify-content:center;margin-top:30px}}
.download-btn-large{{display:flex;align-items:center;gap:10px;padding:16px 32px;background:{user_bubble_gradient};border:none;border-radius:30px;color:#fff;font-size:18px;font-weight:600;cursor:pointer;box-shadow:0 4px 15px rgba(74,222,128,0.4),0 0 30px rgba(96,165,250,0.3);animation:ps 1.2s infinite}}
.download-btn-large svg{{width:24px;height:24px;fill:white;animation:db 1.2s infinite}}
@keyframes db{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(3px)}}}}
@keyframes ps{{0%,100%{{transform:scale(1);box-shadow:0 4px 15px rgba(74,222,128,0.4),0 0 30px rgba(96,165,250,0.3)}}50%{{transform:scale(1.08);box-shadow:0 6px 25px rgba(74,222,128,0.6),0 0 50px rgba(96,165,250,0.5)}}}}
.end-hint{{font-size:14px;color:rgba(255,255,255,0.8);margin-top:20px;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.5}}}}
/* 横屏模糊背景层 */
.video-bg-blur{{display:none;position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;filter:blur(12px) brightness(0.35);z-index:0;pointer-events:none;transform:scale(1.05)}}
/* 横屏布局 */
@media(orientation:landscape){{
  .video-bg-blur{{display:block}}
  .root{{display:flex;flex-direction:row}}
  /* 视频区：contain 完整显示，边缘渐变融入模糊背景 */
  .video-bg{{position:relative;width:50%;height:100vh;object-fit:contain;flex-shrink:0;z-index:1;-webkit-mask-image:linear-gradient(to right,transparent 0%,black 3%,black 95%,transparent 100%);mask-image:linear-gradient(to right,transparent 0%,black 3%,black 95%,transparent 100%)}}
  .gradient-overlay{{z-index:2;pointer-events:none;background:linear-gradient(to right,transparent 0%,transparent 45%,rgba(0,0,0,0.7) 50%,rgba(0,0,0,0.88) 55%,rgba(0,0,0,0.92) 100%)}}
  /* 聊天区 */
  .page2{{position:relative;width:50%;height:100vh;display:flex;flex-direction:column;z-index:3}}
  .chat-header{{position:relative;top:auto;padding:1.5vh 0;flex-shrink:0;gap:8px}}
  .header-avatar{{width:min(32px,8vh);height:min(32px,8vh);border-radius:8px}}
  .header-name{{font-size:min(14px,4vh)}}
  .chat-container{{position:relative;top:auto;bottom:auto;flex:1;min-height:0;padding:1vh 2vw}}
  .chat-message{{margin-bottom:min(6px,1.2vh)}}
  .message-sender{{font-size:min(11px,3vh)}}
  .message-content{{padding:min(7px,1.8vh) min(10px,2vw);font-size:min(13px,3.5vh);border-radius:min(14px,3.5vh)}}
  .message-meta{{font-size:min(9px,2.2vh)}}
  .input-area{{position:relative;flex-shrink:0;padding:0.5vh 2vw 1vh}}
  .input-box{{padding:0.6vh 2vw;margin-bottom:0.5vh}}
  .input-field{{font-size:min(13px,3.2vh)}}
  .send-btn{{width:min(28px,6.5vh);height:min(28px,6.5vh);flex-shrink:0}}
  .send-btn svg{{width:min(14px,3.2vh);height:min(14px,3.2vh)}}
  /* 键盘：max-width 480px 限制拉伸，居中 */
  .virtual-keyboard{{max-width:480px;margin:0 auto;padding:0.3vh 0.5vw}}
  .keyboard-row{{margin-bottom:min(3px,0.6vh);gap:min(3px,0.5vw)}}
  .key{{height:min(28px,5.5vh);font-size:min(12px,3vh);max-width:42px}}
  .key.wide{{max-width:52px}}
  .key.space{{max-width:none}}
  .key.send{{max-width:none}}
  .end-page{{width:50%;left:50%;z-index:4}}
  .end-logo{{width:min(60px,15vh);height:min(60px,15vh);border-radius:min(16px,4vh);margin-bottom:min(10px,2vh)}}
  .end-title{{font-size:min(18px,5vh)}}
  .end-desc{{font-size:min(12px,3vh);margin-bottom:min(15px,3vh)}}
  .download-btn-large{{padding:min(10px,2vh) min(20px,4vw);font-size:min(14px,3.5vh);border-radius:min(20px,5vh)}}
}}
.orientation-hint{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:#000;z-index:9999;flex-direction:column;align-items:center;justify-content:center;color:#fff;text-align:center;padding:20px}}
{'@media(orientation:landscape) and (max-height:500px){.orientation-hint{display:flex}}' if platform != 'google' else ''}
</style>
</head>
<body>
{'<div class="orientation-hint"><p>' + ui['rotate'] + '</p></div>' if platform != 'google' else ''}
<div class="root">
<video class="video-bg-blur" id="bgVideoBlur" autoplay loop muted playsinline></video>
<video class="video-bg" id="bgVideo" autoplay loop muted playsinline preload="auto"
  {video_src_attr}></video>
<div class="gradient-overlay"></div>
<div class="page page2 active" id="page2">
<div class="chat-header">
  <img src="{logo_data}" alt="AI" class="header-avatar" id="headerAvatar" loading="lazy">
  <div class="header-info"><div class="header-name">{ai_name}</div></div>
</div>
<div class="chat-container" id="chatContainer"></div>
<div class="input-area">
  <div class="input-box">
    <input type="text" class="input-field" id="textInput" placeholder="{ui['placeholder']}" readonly>
    <button class="send-btn" id="sendBtn"><svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg></button>
  </div>
  <div class="virtual-keyboard" id="virtualKeyboard">
    <div class="keyboard-row">
      <button class="key" data-key="q">q</button><button class="key" data-key="w">w</button>
      <button class="key" data-key="e">e</button><button class="key" data-key="r">r</button>
      <button class="key" data-key="t">t</button><button class="key" data-key="y">y</button>
      <button class="key" data-key="u">u</button><button class="key" data-key="i">i</button>
      <button class="key" data-key="o">o</button><button class="key" data-key="p">p</button>
    </div>
    <div class="keyboard-row">
      <button class="key" data-key="a">a</button><button class="key" data-key="s">s</button>
      <button class="key" data-key="d">d</button><button class="key" data-key="f">f</button>
      <button class="key" data-key="g">g</button><button class="key" data-key="h">h</button>
      <button class="key" data-key="j">j</button><button class="key" data-key="k">k</button>
      <button class="key" data-key="l">l</button>
    </div>
    <div class="keyboard-row">
      <button class="key wide" id="shiftKey">⇧</button>
      <button class="key" data-key="z">z</button><button class="key" data-key="x">x</button>
      <button class="key" data-key="c">c</button><button class="key" data-key="v">v</button>
      <button class="key" data-key="b">b</button><button class="key" data-key="n">n</button>
      <button class="key" data-key="m">m</button>
      <button class="key wide" id="backspaceKey">⌫</button>
    </div>
    <div class="keyboard-row">
      <button class="key" id="numKey">123</button>
      <button class="key space" data-key=" ">{ui['space']}</button>
      <button class="key send" id="keyboardSend">{ui['send']}</button>
    </div>
  </div>
</div>
</div>
<div class="end-page" id="endPage">
  <div class="end-content">
    <img src="{logo_data}" alt="{app_name}" class="end-logo" loading="lazy">
    <h2 class="end-title">{endcard.get('title', 'Discover Your AI Soulmate')}</h2>
    <p class="end-desc">{end_desc_html}</p>
    <div class="download-section">
      <button class="download-btn-large" id="downloadBtn">
        <svg viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
        {endcard.get('ctaText', 'Download')}
      </button>
    </div>
    <p class="end-hint">{ui['hint']}</p>
  </div>
</div>
</div>
{platform_body_script}
<script>
(function(){{
var MESSAGES={messages_json};
var AI_NAME="{ai_name}";
var UI_TEXT={{you:"{ui['you']}",typing:"{ui['typing']}",read:"{ui['read']}"}};
var TIMING={{typingDuration:{typing_duration},messageGap:{message_gap},autoEndDelay:{auto_end_delay}}};
var chatContainer=document.getElementById('chatContainer');
var textInput=document.getElementById('textInput');
var sendBtn=document.getElementById('sendBtn');
var endPage=document.getElementById('endPage');
var bgVideo=document.getElementById('bgVideo');
var shiftKey=document.getElementById('shiftKey');
var backspaceKey=document.getElementById('backspaceKey');
var keyboardSend=document.getElementById('keyboardSend');
var state={{msgIndex:0,userClicks:0,isShiftOn:false,isTyping:false,playbackDone:false}};
var audioCtx=null;

function playSound(freq,dur){{try{{if(!audioCtx)audioCtx=new(window.AudioContext||window.webkitAudioContext)();var o=audioCtx.createOscillator(),g=audioCtx.createGain();o.connect(g);g.connect(audioCtx.destination);o.frequency.setValueAtTime(freq,audioCtx.currentTime);g.gain.setValueAtTime(0.2,audioCtx.currentTime);g.gain.exponentialRampToValueAtTime(0.01,audioCtx.currentTime+dur);o.start(audioCtx.currentTime);o.stop(audioCtx.currentTime+dur)}}catch(e){{}}}}
function delay(ms){{return new Promise(function(r){{setTimeout(r,ms)}})}};

function addMessage(type,text){{
  return new Promise(function(resolve){{
    var d=document.createElement('div');d.className='chat-message '+type;
    var sender=type==='ai'?AI_NAME:UI_TEXT.you;
    var t=new Date().toLocaleTimeString('en-US',{{hour:'2-digit',minute:'2-digit',hour12:false}});
    d.innerHTML='<div class="message-sender">'+sender+'</div><div class="message-content">'+text+'</div><div class="message-meta"><span>'+t+'</span><span class="message-status">'+UI_TEXT.read+'</span></div>';
    chatContainer.appendChild(d);d.offsetHeight;d.classList.add('show');
    playSound(800,0.1);chatContainer.scrollTop=chatContainer.scrollHeight;
    setTimeout(resolve,300);
  }});
}}

function showTyping(){{
  var d=document.createElement('div');d.className='chat-message ai';d.id='typingIndicator';
  d.innerHTML='<div class="message-sender">'+AI_NAME+'</div><div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div><span class="typing-text">'+UI_TEXT.typing+'</span></div>';
  chatContainer.appendChild(d);d.offsetHeight;d.classList.add('show');
  chatContainer.scrollTop=chatContainer.scrollHeight;
}}

function removeTyping(){{var el=document.getElementById('typingIndicator');if(el)el.remove()}}

function openStore(){{
  {cta_js}
  {cta_fallback}
}}

function showEndPage(){{
  endPage.classList.add('active');
  endPage.addEventListener('click',openStore);
  setTimeout(openStore,TIMING.autoEndDelay);
}}

function processMessage(){{
  if(state.msgIndex>=MESSAGES.length){{showEndPage();return}}
  var msg=MESSAGES[state.msgIndex];
  if(msg.type==='ai'){{
    if(state.msgIndex>0){{
      showTyping();
      setTimeout(function(){{removeTyping();setTimeout(function(){{
        addMessage('ai',msg.content).then(function(){{state.msgIndex++;processMessage()}});
      }},TIMING.messageGap)}},TIMING.typingDuration);
    }}else{{
      addMessage('ai',msg.content).then(function(){{state.msgIndex++;processMessage()}});
    }}
  }}else if(msg.type==='user_trigger'||msg.type==='user_trigger_end'){{
    state._userResolve=function(){{
      if(msg.type==='user_trigger_end'){{showEndPage();return}}
      state.msgIndex++;processMessage();
    }};
  }}else{{state.msgIndex++;processMessage()}}
}}

function handleSend(){{
  var text=textInput.value.trim();
  if(!text||state.isTyping)return;
  state.isTyping=true;textInput.value='';
  playSound(400,0.05);
  var curMsg=MESSAGES[state.msgIndex];
  if(curMsg&&curMsg.type==='user_trigger_end'){{
    state.userClicks++;state.isTyping=false;
    if(state._userResolve){{var r=state._userResolve;state._userResolve=null;r()}}
    return;
  }}
  addMessage('user',text).then(function(){{
    state.userClicks++;state.isTyping=false;
    if(state._userResolve){{var r=state._userResolve;state._userResolve=null;r()}}
  }});
}}

// 键盘
document.querySelectorAll('.key[data-key]').forEach(function(k){{
  k.addEventListener('click',function(){{
    var v=k.getAttribute('data-key');
    if(v===' ')textInput.value+=' ';
    else if(/[a-z]/.test(v)){{textInput.value+=state.isShiftOn?v.toUpperCase():v;if(state.isShiftOn){{state.isShiftOn=false;shiftKey.style.background='rgba(255,255,255,0.15)';document.querySelectorAll('.key[data-key]').forEach(function(k2){{var c=k2.getAttribute('data-key');if(c.length===1&&/[a-z]/.test(c))k2.textContent=c}})}}}}
    else textInput.value+=v;
    playSound(1200,0.03);k.classList.add('pressed');setTimeout(function(){{k.classList.remove('pressed')}},100);
  }});
}});
shiftKey.addEventListener('click',function(){{
  playSound(1200,0.03);state.isShiftOn=!state.isShiftOn;
  shiftKey.style.background=state.isShiftOn?'linear-gradient(135deg,#F472B6,#60A5FA)':'rgba(255,255,255,0.15)';
  document.querySelectorAll('.key[data-key]').forEach(function(k){{var c=k.getAttribute('data-key');if(c.length===1&&/[a-z]/.test(c))k.textContent=state.isShiftOn?c.toUpperCase():c}});
}});
backspaceKey.addEventListener('click',function(){{playSound(1200,0.03);textInput.value=textInput.value.slice(0,-1)}});
keyboardSend.addEventListener('click',handleSend);
sendBtn.addEventListener('click',handleSend);

bgVideo.play().catch(function(){{}});
var bgBlur=document.getElementById('bgVideoBlur');
if(bgBlur&&bgVideo.src){{bgBlur.src=bgVideo.src;bgBlur.play().catch(function(){{}})}}
document.addEventListener('visibilitychange',function(){{if(document.hidden){{bgVideo.pause();if(bgBlur)bgBlur.pause()}}else{{bgVideo.play();if(bgBlur)bgBlur.play()}}}});
document.addEventListener('touchstart',function(){{}},{{passive:true}});

{_generate_bgm_js(bgm_style) if bgm_enabled else ''}

// 初始化
setTimeout(function(){{processMessage()}},500);
document.getElementById('downloadBtn').addEventListener('click',openStore);
}})();
</script>
</body>
</html>'''
    return html, video_file_path


# ---------- 导出接口 ----------

@app.route('/api/export', methods=['POST'])
def export_playable():
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400

    config = data.get('config', {})
    platform = data.get('platform', 'all')  # tiktok / google / facebook / all
    locales = data.get('locales', [])  # 本地化地区列表
    app_name = config.get('appName', 'MiraiMind')
    date_str = datetime.datetime.now().strftime('%Y%m%d')

    platforms = ['tiktok', 'google', 'facebook'] if platform == 'all' else [platform]
    results = []

    # 构建导出任务列表：原始 + 各 locale 翻译版本
    base_locale = config.get('locale', 'EN')
    export_configs = [{'locale': base_locale, 'config': config, 'is_extra': False}]
    for locale in locales:
        try:
            new_msgs, new_endcard = localize_content(
                config.get('messages', []),
                config.get('endcard', {}),
                locale
            )
            loc_config = json.loads(json.dumps(config))
            loc_config['messages'] = new_msgs
            loc_config['endcard'] = new_endcard
            loc_config['locale'] = locale
            export_configs.append({'locale': locale, 'config': loc_config, 'is_extra': True})
        except Exception as e:
            print(f'[警告] 本地化失败 ({locale}): {e}')

    for ec in export_configs:
        cur_config = ec['config']
        locale = ec['locale']
        is_extra = ec['is_extra']
        # 只有额外翻译版本文件名才加 locale 标签
        locale_tag = f'_{locale}' if is_extra else ''

        for plat in platforms:
            html_content, _vf = generate_playable_html(cur_config, plat, locale=locale)

            out_filename = f"{app_name}_Playable_{plat.capitalize()}{locale_tag}_{date_str}.zip"
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('index.html', html_content)
                if plat == 'tiktok':
                    zf.writestr('config.json', json.dumps({
                        "playable_orientation": 0
                    }, indent=2))
            out_data = buf.getvalue()

            size_kb = len(out_data) / 1024
            label = f'{plat}' + (f' ({locale})' if is_extra else '')
            results.append({
                'platform': label,
                'filename': out_filename,
                'size': f'{size_kb:.1f} KB',
                'sizeBytes': len(out_data),
                'data': base64.b64encode(out_data).decode('ascii')
            })

    return jsonify({'results': results})


@app.route('/api/download/<filename>')
def download_file(filename):
    # 安全检查
    safe_name = Path(filename).name
    file_path = OUTPUT_DIR / safe_name
    if not file_path.exists():
        return jsonify({'error': '文件不存在'}), 404
    return send_file(str(file_path), as_attachment=True, download_name=safe_name)


# ---------- 自动更新 ----------

VERSION_FILE = BASE_DIR / 'version.json'


def _get_local_version_info() -> dict:
    """读取本地版本信息"""
    if VERSION_FILE.exists():
        try:
            return json.loads(VERSION_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'version': APP_VERSION, 'commit': '', 'updated_at': ''}


def _save_local_version_info(info: dict):
    VERSION_FILE.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')


def _github_api(endpoint: str) -> dict:
    """调用 GitHub API"""
    url = f'https://api.github.com/repos/{GITHUB_REPO}{endpoint}'
    req = urllib.request.Request(url, headers={
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'PlayableEditor-Updater'
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


@app.route('/api/version')
def get_version():
    """返回当前本地版本"""
    info = _get_local_version_info()
    info['version'] = APP_VERSION
    return jsonify(info)


@app.route('/api/check-update')
def check_update():
    """检查 GitHub 上是否有新版本"""
    try:
        local_info = _get_local_version_info()
        local_commit = local_info.get('commit', '')

        # 获取远程最新 commit
        remote = _github_api('/commits/main')
        remote_sha = remote['sha']
        remote_msg = remote['commit']['message'].split('\n')[0]
        remote_date = remote['commit']['committer']['date']

        has_update = (local_commit != remote_sha) if local_commit else True

        return jsonify({
            'hasUpdate': has_update,
            'local': local_info,
            'remote': {
                'commit': remote_sha,
                'message': remote_msg,
                'date': remote_date
            }
        })
    except Exception as e:
        return jsonify({'error': f'检查更新失败: {e}'}), 500


@app.route('/api/do-update', methods=['POST'])
def do_update():
    """从 GitHub 下载最新代码并替换本地文件"""
    try:
        # 1. 获取最新 commit SHA
        remote = _github_api('/commits/main')
        remote_sha = remote['sha']
        remote_msg = remote['commit']['message'].split('\n')[0]

        # 2. 下载 ZIP 包
        zip_url = f'https://api.github.com/repos/{GITHUB_REPO}/zipball/main'
        req = urllib.request.Request(zip_url, headers={
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'PlayableEditor-Updater'
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            zip_data = resp.read()

        # 3. 解压到临时目录
        tmp_dir = BASE_DIR / '_update_tmp'
        if tmp_dir.exists():
            shutil.rmtree(str(tmp_dir))
        tmp_dir.mkdir()

        buf = io.BytesIO(zip_data)
        with zipfile.ZipFile(buf, 'r') as zf:
            zf.extractall(str(tmp_dir))

        # GitHub ZIP 内有一层目录（如 oNa2O2o-playable-editor-abc1234/）
        inner_dirs = [d for d in tmp_dir.iterdir() if d.is_dir()]
        if not inner_dirs:
            return jsonify({'error': '更新包结构异常'}), 500
        src_dir = inner_dirs[0]

        # 4. 需要更新的文件列表（排除用户数据）
        update_files = [
            'app.py',
            'requirements.txt',
            'start.bat',
            'static/editor.css',
            'static/editor.js',
            'templates/index.html',
            'templates/preview.html',
        ]

        updated = []
        for rel_path in update_files:
            src_file = src_dir / rel_path
            dst_file = BASE_DIR / rel_path
            if src_file.exists():
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_file), str(dst_file))
                updated.append(rel_path)

        # 同时复制新增的文件（如 .gitignore, version.json 等）
        for item in src_dir.rglob('*'):
            if item.is_file():
                rel = item.relative_to(src_dir)
                rel_str = str(rel).replace('\\', '/')
                # 跳过已处理的和用户数据目录
                if rel_str in update_files:
                    continue
                if any(rel_str.startswith(skip) for skip in ['configs/', 'output/', 'static/uploads/', '__pycache__/']):
                    continue
                dst = BASE_DIR / rel
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(item), str(dst))
                    updated.append(rel_str)

        # 5. 清理临时目录
        shutil.rmtree(str(tmp_dir), ignore_errors=True)

        # 6. 保存版本信息
        _save_local_version_info({
            'version': APP_VERSION,
            'commit': remote_sha,
            'message': remote_msg,
            'updated_at': datetime.datetime.now().isoformat()
        })

        return jsonify({
            'ok': True,
            'commit': remote_sha,
            'message': remote_msg,
            'updatedFiles': updated,
            'needRestart': True
        })
    except Exception as e:
        # 清理
        tmp_dir = BASE_DIR / '_update_tmp'
        if tmp_dir.exists():
            shutil.rmtree(str(tmp_dir), ignore_errors=True)
        return jsonify({'error': f'更新失败: {e}'}), 500


def _open_browser(port: int):
    """延迟 1.5 秒后自动打开浏览器"""
    import threading
    import webbrowser

    def _open():
        import time
        time.sleep(1.5)
        webbrowser.open(f'http://127.0.0.1:{port}')

    threading.Thread(target=_open, daemon=True).start()


if __name__ == '__main__':
    # 初始化版本文件
    if not VERSION_FILE.exists():
        _save_local_version_info({
            'version': APP_VERSION,
            'commit': '',
            'updated_at': ''
        })
    port = 5000
    print('=' * 40)
    print(f'  Playable Ad Editor v{APP_VERSION}')
    print(f'  http://127.0.0.1:{port}')
    print('=' * 40)
    _open_browser(port)
    app.run(debug=False, port=port, host='0.0.0.0')
