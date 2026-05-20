"""批量导出试玩广告 — 2026年5月8日素材 v2（使用角色形象标签命名）"""
import sys
import os
import json
import zipfile
import io
import shutil
from pathlib import Path

# 修复 Windows 控制台中文编码问题
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 确保能导入 app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(str(Path(__file__).resolve().parent))

from app import generate_playable_html, compress_video, url_to_base64, UPLOAD_DIR, COMPRESSED_DIR

# ========== 配置区 ==========

# 输出目录
OUTPUT_BASE = Path(r"D:\试玩广告制作\2026年5月8日\输出")

# 素材源目录
SOURCE_DIR = Path(r"D:\试玩广告制作\2026年5月8日\素材")

# 视频素材 — 使用角色形象标签
VIDEOS = [
    # 女性向素材
    {
        "path": SOURCE_DIR / "女性向.mp4",
        "tag": "黑发西装冷峻",  # 角色形象标签
        "gender": "女性向",  # 性向标识
        "name_TC": "夜澤",
        "name_JP": "夜沢（よざわ）",
        "name_EN": "Yozawa",
    },
    {
        "path": SOURCE_DIR / "女性向1.mp4",
        "tag": "白发温柔微笑",
        "gender": "女性向",
        "name_TC": "凜",
        "name_JP": "凛（りん）",
        "name_EN": "Rin",
    },
    {
        "path": SOURCE_DIR / "女性向2.mp4",
        "tag": "金发阳光少年",
        "gender": "女性向",
        "name_TC": "晨曦",
        "name_JP": "朝陽（あさひ）",
        "name_EN": "Asahi",
    },
    {
        "path": SOURCE_DIR / "女性向3.mp4",
        "tag": "紫发神秘优雅",
        "gender": "女性向",
        "name_TC": "星夜",
        "name_JP": "星夜（せいや）",
        "name_EN": "Seiya",
    },
    {
        "path": SOURCE_DIR / "女性向4.mp4",
        "tag": "蓝发清冷少年",
        "gender": "女性向",
        "name_TC": "蒼",
        "name_JP": "蒼（あおい）",
        "name_EN": "Aoi",
    },
    # 男性向素材
    {
        "path": SOURCE_DIR / "男性向.mp4",
        "tag": "粉发甜美少女",
        "gender": "男性向",
        "name_TC": "櫻",
        "name_JP": "桜（さくら）",
        "name_EN": "Sakura",
    },
]

# 语言版本（消息模板，endcard 中的角色名在循环中动态替换）
LOCALES = {
    "TC": {
        "messages": [
            {"id": "msg_1", "type": "ai", "content": "其實，我有一件瞞了你很久的事……", "delayAfterPrev": 500},
            {"id": "msg_2", "type": "user_trigger", "content": "", "delayAfterPrev": 200},
            {"id": "msg_3", "type": "ai", "content": "你現在身邊有人嗎？", "delayAfterPrev": 500},
            {"id": "msg_4", "type": "user_trigger_end", "content": "", "delayAfterPrev": 200},
        ],
        "endcard": {
            "title": "找到你的AI靈魂伴侶",
            "desc": "與{name}和其他AI夥伴，\n展開深度對話",
            "ctaText": "免費下載",
        },
    },
    "JP": {
        "messages": [
            {"id": "msg_1", "type": "ai", "content": "実は、ずっと君に隠していたことがあるんだ……", "delayAfterPrev": 500},
            {"id": "msg_2", "type": "user_trigger", "content": "", "delayAfterPrev": 200},
            {"id": "msg_3", "type": "ai", "content": "今、周りに誰かいる？", "delayAfterPrev": 500},
            {"id": "msg_4", "type": "user_trigger_end", "content": "", "delayAfterPrev": 200},
        ],
        "endcard": {
            "title": "あなたのAIソウルメイトを見つけよう",
            "desc": "{name}や他のAIパートナーと、\n深い会話を始めましょう",
            "ctaText": "無料ダウンロード",
        },
    },
    "EN": {
        "messages": [
            {"id": "msg_1", "type": "ai", "content": "Something I've been hiding from you...", "delayAfterPrev": 500},
            {"id": "msg_2", "type": "user_trigger", "content": "", "delayAfterPrev": 200},
            {"id": "msg_3", "type": "ai", "content": "Is there anyone around you right now?", "delayAfterPrev": 500},
            {"id": "msg_4", "type": "user_trigger_end", "content": "", "delayAfterPrev": 200},
        ],
        "endcard": {
            "title": "Find Your AI Soulmate",
            "desc": "Start deep conversations with\n{name} and other AI partners",
            "ctaText": "Free Download",
        },
    },
}

# 渠道
CHANNELS = {
    "GG": "google",
    "TT": "tiktok",
}

# 基础配置（复用现有产品信息）
BASE_CONFIG = {
    "appName": "MiraiMind",
    "packageName": "com.immomo.miraimind",
    "aiName": "",
    "storeUrl": {
        "android": "https://play.google.com/store/apps/details?id=com.immomo.miraimind",
        "ios": "https://apps.apple.com/us/app/miraimind-real-otaku-energy/id6502377840",
    },
    "assets": {
        "logoUrl": "/static/uploads/logo.png",
        "videoUrl": "",
    },
    "theme": {
        "sendBtnGradient": "linear-gradient(135deg, #F472B6, #60A5FA, #4ADE80, #FBBF24)",
        "aiBubbleBg": "linear-gradient(135deg, rgba(0,0,0,0.7), rgba(0,0,0,0.6))",
        "userBubbleGradient": "linear-gradient(135deg, #4ADE80, #60A5FA)",
        "bgOverlay": "rgba(0,0,0,0.4)",
    },
    "timing": {"typingDuration": 500, "messageGap": 200, "autoEndDelay": 2000},
    "layout": {
        "headerTop": 50, "chatTop": 110, "chatBottom": 280, "chatPadding": 20,
        "bubbleMaxWidth": 75, "bubblePadding": 12, "bubbleBorderRadius": 18,
        "bubbleFontSize": 14, "bubbleOpacity": 1.0, "messageSpacing": 16,
        "senderFontSize": 12, "avatarSize": 44,
    },
    "bgm": {"enabled": True, "style": "dreamy"},
}

# TikTok index.html 解压后不能超约 2.1MB，需要更小的视频压缩目标
TT_MAX_VIDEO_BYTES = 1500 * 1024  # 1500KB
DEFAULT_MAX_VIDEO_BYTES = 2100 * 1024  # 2100KB (GG/FB 用)


def prepare_tt_video(upload_path: Path, tag: str) -> Path:
    """为 TT 渠道准备更小的压缩视频（独立文件名避免缓存冲突）"""
    tt_name = tag + "_tt.mp4"
    tt_upload = UPLOAD_DIR / tt_name
    tt_compressed = COMPRESSED_DIR / (tag + "_tt_compressed.mp4")

    # 已有合格的 TT 压缩版本
    if tt_compressed.exists() and tt_compressed.stat().st_size <= TT_MAX_VIDEO_BYTES:
        return tt_name

    # 复制一份到 uploads 用不同名字，让 compress_video 生成对应的 _compressed 文件
    if not tt_upload.exists():
        shutil.copy2(str(upload_path), str(tt_upload))

    compress_video(str(tt_upload), max_size_bytes=TT_MAX_VIDEO_BYTES)

    if tt_compressed.exists():
        print(f"  [TT视频] {tag}: {tt_compressed.stat().st_size/1024:.0f}KB")
    return tt_name


def main():
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    date_str = "20260518"
    total = len(VIDEOS) * len(LOCALES) * len(CHANNELS)
    done = 0

    for video_info in VIDEOS:
        video_path = Path(video_info["path"])
        video_tag = video_info["tag"]
        gender = video_info["gender"]

        # 将视频复制到 uploads 目录
        safe_name = video_tag + ".mp4"
        upload_path = UPLOAD_DIR / safe_name
        if not upload_path.exists():
            print(f"[复制] {video_path.name} → uploads/{safe_name}")
            shutil.copy2(str(video_path), str(upload_path))

        # 检查默认压缩后是否超 TT 限制
        default_compressed = COMPRESSED_DIR / (video_tag + "_compressed.mp4")
        need_tt_video = False
        if not default_compressed.exists():
            # 先触发一次默认压缩
            compress_video(str(upload_path))
        if default_compressed.exists() and default_compressed.stat().st_size > TT_MAX_VIDEO_BYTES:
            need_tt_video = True
            tt_video_name = prepare_tt_video(upload_path, video_tag)

        for locale_code, locale_data in LOCALES.items():
            char_name = video_info.get(f"name_{locale_code}", "AI")

            for channel_code, platform in CHANNELS.items():
                done += 1
                print(f"\n[{done}/{total}] 生成: {video_tag} / {locale_code} / {channel_code} (角色: {char_name})")

                config = json.loads(json.dumps(BASE_CONFIG))

                # TT 渠道用更小的视频
                if platform == "tiktok" and need_tt_video:
                    config["assets"]["videoUrl"] = f"/static/uploads/{tt_video_name}"
                else:
                    config["assets"]["videoUrl"] = f"/static/uploads/{safe_name}"

                config["locale"] = locale_code
                config["messages"] = locale_data["messages"]
                config["aiName"] = char_name

                endcard = json.loads(json.dumps(locale_data["endcard"]))
                endcard["desc"] = endcard["desc"].format(name=char_name)
                config["endcard"] = endcard

                html_content, _vf = generate_playable_html(config, platform, locale=locale_code)

                # 修改文件名格式：MM_{渠道}_{性向}_{角色形象标签}_{语言}_{日期}.zip
                filename = f"MM_{channel_code}_{gender}_{video_tag}_{locale_code}_{date_str}.zip"
                out_path = OUTPUT_BASE / filename

                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("index.html", html_content)
                    if platform == "tiktok":
                        zf.writestr("config.json", json.dumps({"playable_orientation": 0}, indent=2))

                with open(str(out_path), "wb") as f:
                    f.write(buf.getvalue())

                size_kb = out_path.stat().st_size / 1024
                # 检查 index.html 解压大小
                with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zcheck:
                    html_size = zcheck.getinfo("index.html").file_size
                print(f"  ✓ {filename} (ZIP: {size_kb:.0f}KB, HTML: {html_size/1024:.0f}KB)")

    print(f"\n{'='*50}")
    print(f"全部完成！共 {total} 个文件")
    print(f"输出目录: {OUTPUT_BASE}")


if __name__ == "__main__":
    main()
