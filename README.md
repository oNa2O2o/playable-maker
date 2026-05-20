# Playable Maker - 试玩广告批量生成工具

基于 Perplexity 方法论创建的 Claude Code Skill，用于批量生成多语言、多渠道的试玩广告包。

## 功能特性

- 🎭 **自动角色识别**：扫描视频素材，识别角色特征并命名
- 🌍 **多语言支持**：自动生成繁体中文、日文、英文三个版本
- 📱 **多渠道适配**：支持 Google、TikTok 等主流投放平台
- 🎨 **视觉优先命名**：使用"发色+特征+气质"格式命名角色
- 📦 **批量生成**：一次性生成所有组合的广告包

## 安装依赖

```bash
pip install opencv-python pillow
```

可选（用于视频压缩）：
```bash
# 安装 ffmpeg
# Windows: 下载 https://ffmpeg.org/download.html
# Mac: brew install ffmpeg
# Linux: apt-get install ffmpeg
```

## 使用方法

### 方式一：使用 Skill（推荐）

在 Claude Code 中直接说：

```
做试玩广告，素材在 D:\素材目录
```

或者：

```
/playable-maker
```

### 方式二：直接运行脚本

```bash
cd ~/.claude/skills/playable-maker/scripts
python batch_export.py
```

## 文件结构

```
playable-maker/
├── skill.md                    # Skill 定义文件
├── scripts/
│   ├── playable_generator.py  # 核心生成器
│   └── batch_export.py         # 批量导出脚本
├── templates/                  # HTML 模板（可选）
└── README.md                   # 本文件
```

## 配置说明

### 视频素材要求

- 格式：MP4
- 比例：竖屏 9:16（推荐 1080x1920）
- 时长：5-15秒
- 大小：原始文件 < 10MB

### 角色命名规则

使用"视觉特征"命名，例如：
- `黑发西装冷峻`
- `白发温柔微笑`
- `粉发甜美少女`

### 文件命名格式

```
MM_{渠道}_{性向}_{角色标签}_{语言}_{日期}.zip
```

示例：
- `MM_GG_女性向_黑发西装冷峻_TC_20260518.zip`
- `MM_TT_男性向_粉发甜美少女_JP_20260518.zip`

## 输出说明

每次生成会产生：
- 多个 ZIP 广告包（可直接上传到广告平台）
- 生成说明文档（包含角色列表、使用说明）
- 视频预览图（用于确认角色）

## 技术规格

### 压缩目标
- Google (GG)：2100KB（约 2MB）
- TikTok (TT)：1500KB（约 1.5MB）

### 支持的语言
- TC：繁体中文
- JP：日文（含假名注音）
- EN：英文

### 支持的渠道
- GG：Google Ads
- TT：TikTok Ads

## 故障排除

### 问题：视频压缩失败
**解决**：安装 ffmpeg 或使用原视频（会自动降级）

### 问题：中文乱码
**解决**：脚本已内置 UTF-8 编码修复

### 问题：生成的文件太大
**解决**：
1. 压缩原视频
2. 降低视频分辨率
3. 缩短视频时长

## 更新日志

### v1.0.0 (2026-05-20)
- 初始版本
- 支持多语言、多渠道批量生成
- 自动视频压缩
- 角色视觉特征识别

## 许可证

MIT License

## 作者

Created with Claude Code using Perplexity methodology
