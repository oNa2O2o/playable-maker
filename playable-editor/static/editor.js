/**
 * 试玩广告编辑器 — 核心 JS
 */
(function () {
  'use strict';

  // ========== 默认配置 ==========
  const DEFAULT_CONFIG = {
    appName: 'MiraiMind',
    packageName: 'com.immomo.miraimind',
    storeUrl: {
      android: 'https://play.google.com/store/apps/details?id=com.immomo.miraimind',
      ios: 'https://apps.apple.com/us/app/miraimind-real-otaku-energy/id6502377840'
    },
    aiName: '橘 ひまり',
    locale: 'JP',
    assets: {
      logoUrl: 'https://oversea.hellogroupcdn.com/s1/u/ibjjeahbh/loveRo/LOGO2.png',
      videoUrl: '/static/uploads/3D分解_俯视角_墙角.mp4'
    },
    theme: {
      sendBtnGradient: 'linear-gradient(135deg, #F472B6, #60A5FA, #4ADE80, #FBBF24)',
      aiBubbleBg: 'linear-gradient(135deg, rgba(0,0,0,0.7), rgba(0,0,0,0.6))',
      userBubbleGradient: 'linear-gradient(135deg, #4ADE80, #60A5FA)',
      bgOverlay: 'rgba(0,0,0,0.4)'
    },
    messages: [
      { id: 'msg_1', content: '行き場、なくて。', type: 'ai', delayAfterPrev: 500 },
      { id: 'msg_2', content: '', type: 'user_trigger', delayAfterPrev: 0 },
      { id: 'msg_3', content: '今夜だけ、いい？', type: 'ai', delayAfterPrev: 500 },
      { id: 'msg_4', content: '', type: 'user_trigger_end', delayAfterPrev: 0 }
    ],
    layout: {
      headerTop: 50, chatTop: 110, chatBottom: 280, chatPadding: 20,
      bubbleMaxWidth: 75, bubblePadding: 12, bubbleBorderRadius: 18,
      bubbleFontSize: 14, bubbleOpacity: 1.0, messageSpacing: 16,
      senderFontSize: 12, avatarSize: 44
    },
    timing: { typingDuration: 500, messageGap: 200, autoEndDelay: 2000 },
    endcard: {
      title: 'あなたのAIソウルメイトを見つけよう',
      desc: 'エリックや他のAIパートナーと、\n深い会話を始めよう',
      ctaText: 'ダウンロード'
    }
  };

  // ========== 当前配置(深拷贝) ==========
  let config = JSON.parse(JSON.stringify(DEFAULT_CONFIG));
  let msgIdCounter = 100;
  let editingMsgId = null;
  let previewReady = false;

  // ========== DOM helpers ==========
  const $ = id => document.getElementById(id);
  const previewFrame = $('previewFrame');

  // ========== 折叠面板 ==========
  window.toggleSection = function (id) {
    const sec = document.getElementById(id);
    if (sec) sec.classList.toggle('collapsed');
  };

  // ========== 配置读取/写入 ==========
  function readConfigFromUI() {
    // 简单字段
    config.appName = $('cfgAppName').value;
    config.packageName = $('cfgPackageName').value;
    config.storeUrl.android = $('cfgStoreAndroid').value;
    config.storeUrl.ios = $('cfgStoreIos').value;
    config.aiName = $('cfgAiName').value;
    config.locale = $('cfgLocale').value;
    config.assets.logoUrl = $('cfgLogoUrl').value;
    config.assets.videoUrl = $('cfgVideoUrl').value;
    config.theme.sendBtnGradient = $('cfgSendBtnGradient').value;
    config.theme.aiBubbleBg = $('cfgAiBubbleBg').value;
    config.theme.userBubbleGradient = $('cfgUserBubbleGradient').value;
    config.theme.bgOverlay = $('cfgBgOverlay').value;
    config.timing.typingDuration = parseInt($('cfgTypingDuration').value) || 500;
    config.timing.messageGap = parseInt($('cfgMessageGap').value) || 200;
    config.timing.autoEndDelay = parseInt($('cfgAutoEndDelay').value) || 2000;
    config.endcard.title = $('cfgEndTitle').value;
    config.endcard.desc = $('cfgEndDesc').value;
    config.endcard.ctaText = $('cfgEndCta').value;
    // 布局参数
    if (!config.layout) config.layout = {};
    config.layout.headerTop = parseInt($('cfgHeaderTop').value) || 50;
    config.layout.chatTop = parseInt($('cfgChatTop').value) || 110;
    config.layout.chatBottom = parseInt($('cfgChatBottom').value) || 280;
    config.layout.chatPadding = parseInt($('cfgChatPadding').value) || 20;
    config.layout.bubbleMaxWidth = parseInt($('cfgBubbleMaxWidth').value) || 75;
    config.layout.bubblePadding = parseInt($('cfgBubblePadding').value) || 12;
    config.layout.bubbleBorderRadius = parseInt($('cfgBubbleBorderRadius').value) || 18;
    config.layout.bubbleFontSize = parseInt($('cfgBubbleFontSize').value) || 14;
    config.layout.bubbleOpacity = parseInt($('cfgBubbleOpacity').value) * 0.01;
    config.layout.messageSpacing = parseInt($('cfgMessageSpacing').value) || 16;
    config.layout.senderFontSize = parseInt($('cfgSenderFontSize').value) || 12;
    config.layout.avatarSize = parseInt($('cfgAvatarSize').value) || 44;
    // BGM
    if (!config.bgm) config.bgm = {};
    config.bgm.enabled = $('cfgBgmEnabled').checked;
    config.bgm.style = $('cfgBgmStyle').value;
  }

  function writeConfigToUI() {
    $('cfgAppName').value = config.appName || '';
    $('cfgPackageName').value = config.packageName || '';
    $('cfgStoreAndroid').value = config.storeUrl?.android || '';
    $('cfgStoreIos').value = config.storeUrl?.ios || '';
    $('cfgAiName').value = config.aiName || '';
    $('cfgLocale').value = config.locale || 'EN';
    $('cfgLogoUrl').value = config.assets?.logoUrl || '';
    $('cfgVideoUrl').value = config.assets?.videoUrl || '';
    $('cfgSendBtnGradient').value = config.theme?.sendBtnGradient || '';
    $('cfgAiBubbleBg').value = config.theme?.aiBubbleBg || '';
    $('cfgUserBubbleGradient').value = config.theme?.userBubbleGradient || '';
    $('cfgBgOverlay').value = config.theme?.bgOverlay || '';
    $('cfgTypingDuration').value = config.timing?.typingDuration || 500;
    $('cfgMessageGap').value = config.timing?.messageGap || 200;
    $('cfgAutoEndDelay').value = config.timing?.autoEndDelay || 2000;
    $('cfgEndTitle').value = config.endcard?.title || '';
    $('cfgEndDesc').value = config.endcard?.desc || '';
    $('cfgEndCta').value = config.endcard?.ctaText || '';
    // 布局参数
    const ly = config.layout || {};
    setSlider('cfgHeaderTop', ly.headerTop ?? 50);
    setSlider('cfgChatTop', ly.chatTop ?? 110);
    setSlider('cfgChatBottom', ly.chatBottom ?? 280);
    setSlider('cfgChatPadding', ly.chatPadding ?? 20);
    setSlider('cfgBubbleMaxWidth', ly.bubbleMaxWidth ?? 75);
    setSlider('cfgBubblePadding', ly.bubblePadding ?? 12);
    setSlider('cfgBubbleBorderRadius', ly.bubbleBorderRadius ?? 18);
    setSlider('cfgBubbleFontSize', ly.bubbleFontSize ?? 14);
    setSlider('cfgBubbleOpacity', Math.round((ly.bubbleOpacity ?? 1.0) * 100));
    setSlider('cfgMessageSpacing', ly.messageSpacing ?? 16);
    setSlider('cfgSenderFontSize', ly.senderFontSize ?? 12);
    setSlider('cfgAvatarSize', ly.avatarSize ?? 44);
    // BGM
    const bgm = config.bgm || {};
    $('cfgBgmEnabled').checked = !!bgm.enabled;
    $('cfgBgmStyle').value = bgm.style || 'ambient';
    renderMessageList();
  }

  function setSlider(id, val) {
    const el = $(id);
    if (!el) return;
    el.value = val;
    // 更新显示值
    const valId = 'val' + id.replace('cfg', '');
    const valEl = $(valId);
    if (valEl) {
      if (el.dataset.scale) {
        valEl.textContent = (val * parseFloat(el.dataset.scale)).toFixed(2);
      } else {
        valEl.textContent = val;
      }
    }
  }

  // ========== 预览通信 ==========
  function sendToPreview(data) {
    if (previewFrame && previewFrame.contentWindow) {
      previewFrame.contentWindow.postMessage(data, '*');
    }
  }

  function updatePreview() {
    readConfigFromUI();
    sendToPreview({ type: 'updateConfig', config });
  }

  // 监听 previewReady
  window.addEventListener('message', function (e) {
    if (e.data && e.data.type === 'previewReady') {
      previewReady = true;
      updatePreview();
    }
  });

  // ========== 消息列表渲染 ==========
  function renderMessageList() {
    const list = $('messageList');
    list.innerHTML = '';
    config.messages.forEach((msg, idx) => {
      const item = document.createElement('div');
      item.className = 'message-item';
      item.draggable = true;
      item.dataset.idx = idx;
      item.dataset.id = msg.id;

      const typeLabel = msg.type === 'ai' ? 'AI' :
        msg.type === 'user_trigger' ? 'USR' : 'END';
      const typeClass = msg.type === 'ai' ? 'ai' : 'user';
      const delayText = msg.delayAfterPrev ? `${msg.delayAfterPrev}ms` : '';

      if (msg.type === 'ai') {
        // AI 消息：显示可编辑输入框
        item.innerHTML = `
          <span class="msg-drag-handle">⠿</span>
          <span class="msg-type-badge ${typeClass}">${typeLabel}</span>
          <input class="msg-inline-edit" value="${escapeHtml(msg.content || '')}" data-msg-id="${msg.id}" placeholder="输入消息内容...">
          <span class="msg-delay">${delayText}</span>
          <span class="msg-actions">
            <button title="编辑类型/延迟" onclick="editMessage('${msg.id}')">✏</button>
            <button class="delete" title="删除" onclick="deleteMessage('${msg.id}')">✕</button>
          </span>
        `;
        // 绑定行内编辑事件
        const inlineInput = item.querySelector('.msg-inline-edit');
        inlineInput.addEventListener('input', function () {
          const m = config.messages.find(m => m.id === this.dataset.msgId);
          if (m) { m.content = this.value; scheduleUpdate(); }
        });
      } else {
        // trigger 类型：保持标签显示
        const preview = msg.type === 'user_trigger' ? '[等待发送]' : '[结束触发]';
        item.innerHTML = `
          <span class="msg-drag-handle">⠿</span>
          <span class="msg-type-badge ${typeClass}">${typeLabel}</span>
          <span class="msg-preview">${escapeHtml(preview)}</span>
          <span class="msg-delay">${delayText}</span>
          <span class="msg-actions">
            <button title="编辑类型/延迟" onclick="editMessage('${msg.id}')">✏</button>
            <button class="delete" title="删除" onclick="deleteMessage('${msg.id}')">✕</button>
          </span>
        `;
      }

      // 拖拽事件
      item.addEventListener('dragstart', onDragStart);
      item.addEventListener('dragover', onDragOver);
      item.addEventListener('drop', onDrop);
      item.addEventListener('dragend', onDragEnd);
      item.addEventListener('dragleave', onDragLeave);

      list.appendChild(item);
    });
  }

  // ========== 拖拽排序 ==========
  let dragIdx = -1;

  function onDragStart(e) {
    dragIdx = parseInt(e.currentTarget.dataset.idx);
    e.currentTarget.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
  }

  function onDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    e.currentTarget.classList.add('drag-over');
  }

  function onDragLeave(e) {
    e.currentTarget.classList.remove('drag-over');
  }

  function onDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    const targetIdx = parseInt(e.currentTarget.dataset.idx);
    if (dragIdx === targetIdx) return;
    const [moved] = config.messages.splice(dragIdx, 1);
    config.messages.splice(targetIdx, 0, moved);
    renderMessageList();
    updatePreview();
  }

  function onDragEnd(e) {
    e.currentTarget.classList.remove('dragging');
    document.querySelectorAll('.message-item').forEach(el => el.classList.remove('drag-over'));
  }

  // ========== 消息操作 ==========
  function genMsgId() {
    return 'msg_' + (++msgIdCounter);
  }

  window.deleteMessage = function (id) {
    config.messages = config.messages.filter(m => m.id !== id);
    renderMessageList();
    updatePreview();
  };

  window.editMessage = function (id) {
    const msg = config.messages.find(m => m.id === id);
    if (!msg) return;
    editingMsgId = id;
    $('editMsgType').value = msg.type;
    $('editMsgContent').value = msg.content || '';
    $('editMsgDelay').value = msg.delayAfterPrev || 0;
    toggleContentField(msg.type);
    $('msgEditOverlay').classList.add('active');
  };

  function toggleContentField(type) {
    const group = $('editMsgContentGroup');
    group.style.display = (type === 'user_trigger' || type === 'user_trigger_end') ? 'none' : '';
  }

  $('editMsgType').addEventListener('change', function () {
    toggleContentField(this.value);
  });

  $('btnSaveEditMsg').addEventListener('click', function () {
    const msg = config.messages.find(m => m.id === editingMsgId);
    if (!msg) return;
    msg.type = $('editMsgType').value;
    msg.content = $('editMsgContent').value;
    msg.delayAfterPrev = parseInt($('editMsgDelay').value) || 0;
    if (msg.type === 'user_trigger' || msg.type === 'user_trigger_end') {
      msg.content = '';
    }
    $('msgEditOverlay').classList.remove('active');
    editingMsgId = null;
    renderMessageList();
    updatePreview();
  });

  $('btnCancelEditMsg').addEventListener('click', function () {
    $('msgEditOverlay').classList.remove('active');
    editingMsgId = null;
  });

  // 点击遮罩关闭
  $('msgEditOverlay').addEventListener('click', function (e) {
    if (e.target === this) {
      this.classList.remove('active');
      editingMsgId = null;
    }
  });

  // 添加消息按钮
  $('btnAddAiMsg').addEventListener('click', function () {
    config.messages.push({ id: genMsgId(), content: 'New message', type: 'ai', delayAfterPrev: 500 });
    renderMessageList();
    updatePreview();
  });

  $('btnAddUserTrigger').addEventListener('click', function () {
    config.messages.push({ id: genMsgId(), content: '', type: 'user_trigger', delayAfterPrev: 0 });
    renderMessageList();
    updatePreview();
  });

  $('btnAddUserEnd').addEventListener('click', function () {
    config.messages.push({ id: genMsgId(), content: '', type: 'user_trigger_end', delayAfterPrev: 0 });
    renderMessageList();
    updatePreview();
  });

  // ========== 预览控制 ==========
  $('btnPlayPreview').addEventListener('click', function () {
    readConfigFromUI();
    sendToPreview({ type: 'updateConfig', config });
    setTimeout(() => sendToPreview({ type: 'play' }), 100);
  });

  $('btnResetPreview').addEventListener('click', function () {
    sendToPreview({ type: 'reset' });
    setTimeout(() => updatePreview(), 200);
  });

  // ========== 自动更新预览（输入变化时） ==========
  let updateTimer = null;
  function scheduleUpdate() {
    clearTimeout(updateTimer);
    updateTimer = setTimeout(updatePreview, 300);
  }

  // 监听所有 input/textarea/select 变化
  document.querySelectorAll('.edit-panel input, .edit-panel textarea, .edit-panel select').forEach(el => {
    el.addEventListener('input', scheduleUpdate);
    el.addEventListener('change', scheduleUpdate);
  });

  // ========== 文件上传 ==========
  document.querySelectorAll('input[data-upload-target]').forEach(fileInput => {
    fileInput.addEventListener('change', async function () {
      if (!this.files.length) return;
      const targetId = this.dataset.uploadTarget;
      const formData = new FormData();
      formData.append('file', this.files[0]);
      try {
        const resp = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.url) {
          $(targetId).value = data.url;
          scheduleUpdate();
          showToast('上传成功: ' + data.filename, 'success');
        } else {
          showToast('上传失败: ' + (data.error || '未知错误'), 'error');
        }
      } catch (e) {
        showToast('上传出错: ' + e.message, 'error');
      }
    });
  });

  // ========== 导出 ==========

  // 输出目录句柄（File System Access API）
  let outputDirHandle = null;

  $('btnSelectDir').addEventListener('click', async function () {
    if (!window.showDirectoryPicker) {
      showToast('当前浏览器不支持选择目录，请使用 Chrome 或 Edge', 'error');
      return;
    }
    try {
      outputDirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
      $('selectedDirName').textContent = '📂 ' + outputDirHandle.name;
      $('selectedDirName').style.color = 'var(--accent)';
      showToast('已选择输出目录: ' + outputDirHandle.name, 'success');
    } catch (e) {
      if (e.name !== 'AbortError') showToast('选择目录失败', 'error');
    }
  });

  document.querySelectorAll('.export-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      exportPlatform(this.dataset.platform);
    });
  });

  $('btnExportAll').addEventListener('click', function () {
    exportPlatform('all');
  });

  async function ensureOutputDir() {
    if (outputDirHandle) {
      // 验证权限是否还有效
      const perm = await outputDirHandle.queryPermission({ mode: 'readwrite' });
      if (perm === 'granted') return true;
      const req = await outputDirHandle.requestPermission({ mode: 'readwrite' });
      if (req === 'granted') return true;
    }
    // 需要重新选择
    if (!window.showDirectoryPicker) {
      showToast('当前浏览器不支持选择目录，请使用 Chrome 或 Edge', 'error');
      return false;
    }
    try {
      outputDirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
      $('selectedDirName').textContent = '📂 ' + outputDirHandle.name;
      $('selectedDirName').style.color = 'var(--accent)';
      return true;
    } catch (e) {
      if (e.name !== 'AbortError') showToast('请先选择输出目录', 'error');
      return false;
    }
  }

  async function exportPlatform(platform) {
    // 先确保有输出目录
    const dirReady = await ensureOutputDir();
    if (!dirReady) return;

    readConfigFromUI();
    const resultsDiv = $('exportResults');
    resultsDiv.innerHTML = '<span>导出中...</span>';

    const locales = [];
    document.querySelectorAll('.locale-checkbox:checked').forEach(cb => {
      locales.push(cb.value);
    });

    document.querySelectorAll('.export-btn, #btnExportAll').forEach(b => b.classList.add('exporting'));

    try {
      const resp = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config, platform, locales })
      });
      const data = await resp.json();
      if (data.error) {
        resultsDiv.innerHTML = `<span class="error">${data.error}</span>`;
        showToast('导出失败: ' + data.error, 'error');
        return;
      }

      // 解压每个 zip 到输出目录
      let html = '';
      let fileCount = 0;
      for (const r of data.results) {
        try {
          const zipData = Uint8Array.from(atob(r.data), c => c.charCodeAt(0));
          const zip = await JSZip.loadAsync(zipData);

          // 用 zip 文件名（去掉 .zip）作为子文件夹名
          const folderName = r.filename.replace(/\.zip$/i, '');
          const subDir = await outputDirHandle.getDirectoryHandle(folderName, { create: true });

          for (const [name, entry] of Object.entries(zip.files)) {
            if (entry.dir) continue;
            const content = await entry.async('arraybuffer');
            const fileHandle = await subDir.getFileHandle(name, { create: true });
            const writable = await fileHandle.createWritable();
            await writable.write(content);
            await writable.close();
            fileCount++;
          }
          html += `<div class="success">✓ ${r.platform}: ${r.size} → ${folderName}/</div>`;
        } catch (writeErr) {
          html += `<div class="error">✗ ${r.platform}: 写入失败 - ${writeErr.message}</div>`;
        }
      }

      resultsDiv.innerHTML = html;
      showToast(`导出完成！${fileCount} 个文件已保存到「${outputDirHandle.name}」`, 'success');
    } catch (e) {
      resultsDiv.innerHTML = `<span class="error">网络错误: ${e.message}</span>`;
      showToast('导出出错', 'error');
    } finally {
      document.querySelectorAll('.export-btn, #btnExportAll').forEach(b => b.classList.remove('exporting'));
    }
  }

  // ========== 滑块值实时显示 ==========
  document.querySelectorAll('.slider-group input[type="range"]').forEach(slider => {
    slider.addEventListener('input', function () {
      const valId = 'val' + this.id.replace('cfg', '');
      const valEl = $(valId);
      if (valEl) {
        if (this.dataset.scale) {
          valEl.textContent = (parseInt(this.value) * parseFloat(this.dataset.scale)).toFixed(2);
        } else {
          valEl.textContent = this.value;
        }
      }
      scheduleUpdate();
    });
  });

  // ========== 配置管理 ==========
  let currentConfigName = '';

  async function loadConfigList() {
    try {
      const resp = await fetch('/api/configs');
      const data = await resp.json();
      const sel = $('configSelect');
      // 保留第一个 "新建" 选项
      while (sel.options.length > 1) sel.remove(1);
      (data.configs || []).forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.name;
        opt.textContent = `${c.name} (${c.appName}, ${c.messageCount}条)`;
        sel.appendChild(opt);
      });
      // 恢复选中
      if (currentConfigName) sel.value = currentConfigName;
      $('btnDeleteConfig').style.display = currentConfigName ? '' : 'none';
    } catch (e) {
      console.error('加载配置列表失败', e);
    }
  }

  $('configSelect').addEventListener('change', async function () {
    const name = this.value;
    if (!name) {
      // 新建 => 重置为默认
      config = JSON.parse(JSON.stringify(DEFAULT_CONFIG));
      currentConfigName = '';
      writeConfigToUI();
      updatePreview();
      $('btnDeleteConfig').style.display = 'none';
      return;
    }
    try {
      const resp = await fetch(`/api/configs/${encodeURIComponent(name)}`);
      const data = await resp.json();
      if (data.config) {
        config = data.config;
        // 补全缺失字段
        if (!config.layout) config.layout = JSON.parse(JSON.stringify(DEFAULT_CONFIG.layout));
        if (!config.storeUrl) config.storeUrl = {};
        if (!config.assets) config.assets = {};
        if (!config.theme) config.theme = {};
        if (!config.timing) config.timing = {};
        if (!config.endcard) config.endcard = {};
        currentConfigName = name;
        writeConfigToUI();
        updatePreview();
        $('btnDeleteConfig').style.display = '';
        showToast(`已加载配置: ${name}`, 'success');
      }
    } catch (e) {
      showToast('加载配置失败: ' + e.message, 'error');
    }
  });

  $('btnSaveConfig').addEventListener('click', async function () {
    readConfigFromUI();
    let name = currentConfigName;
    if (!name) {
      name = prompt('请输入配置名称:');
      if (!name) return;
    }
    try {
      const resp = await fetch(`/api/configs/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      const data = await resp.json();
      if (data.ok) {
        currentConfigName = data.name;
        await loadConfigList();
        showToast(`配置已保存: ${data.name}`, 'success');
      }
    } catch (e) {
      showToast('保存失败: ' + e.message, 'error');
    }
  });

  $('btnSaveAsConfig').addEventListener('click', async function () {
    readConfigFromUI();
    const name = prompt('请输入新配置名称:');
    if (!name) return;
    try {
      const resp = await fetch(`/api/configs/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      const data = await resp.json();
      if (data.ok) {
        currentConfigName = data.name;
        await loadConfigList();
        showToast(`配置已另存为: ${data.name}`, 'success');
      }
    } catch (e) {
      showToast('保存失败: ' + e.message, 'error');
    }
  });

  $('btnDeleteConfig').addEventListener('click', async function () {
    if (!currentConfigName) return;
    if (!confirm(`确认删除配置 "${currentConfigName}"?`)) return;
    try {
      await fetch(`/api/configs/${encodeURIComponent(currentConfigName)}`, { method: 'DELETE' });
      showToast(`已删除配置: ${currentConfigName}`, 'success');
      currentConfigName = '';
      $('configSelect').value = '';
      $('btnDeleteConfig').style.display = 'none';
      await loadConfigList();
    } catch (e) {
      showToast('删除失败: ' + e.message, 'error');
    }
  });

  // ========== 导入/导出配置 JSON ==========
  $('btnExportJson').addEventListener('click', function () {
    readConfigFromUI();
    const json = JSON.stringify(config, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `playable_config_${config.appName || 'config'}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('配置已导出', 'success');
  });

  $('btnImportJson').addEventListener('click', function () {
    $('importJsonInput').click();
  });

  $('importJsonInput').addEventListener('change', function () {
    if (!this.files.length) return;
    const reader = new FileReader();
    reader.onload = function (e) {
      try {
        const imported = JSON.parse(e.target.result);
        config = Object.assign({}, DEFAULT_CONFIG, imported);
        // 确保嵌套对象完整
        config.storeUrl = Object.assign({}, DEFAULT_CONFIG.storeUrl, imported.storeUrl);
        config.assets = Object.assign({}, DEFAULT_CONFIG.assets, imported.assets);
        config.theme = Object.assign({}, DEFAULT_CONFIG.theme, imported.theme);
        config.timing = Object.assign({}, DEFAULT_CONFIG.timing, imported.timing);
        config.endcard = Object.assign({}, DEFAULT_CONFIG.endcard, imported.endcard);
        if (!Array.isArray(config.messages)) config.messages = DEFAULT_CONFIG.messages;
        writeConfigToUI();
        updatePreview();
        showToast('配置导入成功', 'success');
      } catch (err) {
        showToast('配置文件格式错误: ' + err.message, 'error');
      }
    };
    reader.readAsText(this.files[0]);
    this.value = '';
  });

  // ========== Toast 通知 ==========
  function showToast(msg, type) {
    const toast = document.createElement('div');
    toast.className = `toast ${type || ''}`;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  // ========== 工具函数 ==========
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ========== 检查更新 ==========
  $('btnCheckUpdate').addEventListener('click', async function () {
    const overlay = $('updateOverlay');
    const title = $('updateTitle');
    const content = $('updateContent');
    const actions = $('updateActions');

    title.textContent = '检查更新';
    content.innerHTML = '正在检查...';
    actions.innerHTML = '<button class="btn btn-outline" onclick="document.getElementById(\'updateOverlay\').classList.remove(\'active\')">关闭</button>';
    overlay.classList.add('active');

    try {
      const resp = await fetch('/api/check-update');
      const data = await resp.json();

      if (data.error) {
        content.innerHTML = `<span style="color:var(--danger)">${data.error}</span>`;
        return;
      }

      if (data.hasUpdate) {
        title.textContent = '发现新版本';
        content.innerHTML = `
          <p style="margin-bottom:8px;color:var(--success)">有可用更新！</p>
          <p style="margin-bottom:4px;">最新提交: <code style="background:var(--bg-input);padding:2px 6px;border-radius:4px;font-size:11px;">${data.remote.commit.substring(0, 7)}</code></p>
          <p style="margin-bottom:4px;">说明: ${data.remote.message}</p>
          <p style="font-size:11px;color:var(--text-secondary);">时间: ${new Date(data.remote.date).toLocaleString()}</p>
        `;
        actions.innerHTML = `
          <button class="btn btn-outline" onclick="document.getElementById('updateOverlay').classList.remove('active')">稍后</button>
          <button class="btn btn-primary" id="btnDoUpdate">立即更新</button>
        `;
        $('btnDoUpdate').addEventListener('click', doUpdate);
      } else {
        title.textContent = '已是最新';
        content.innerHTML = '<p style="color:var(--success)">当前已是最新版本，无需更新。</p>';
      }
    } catch (e) {
      content.innerHTML = `<span style="color:var(--danger)">网络错误: ${e.message}</span>`;
    }
  });

  async function doUpdate() {
    const content = $('updateContent');
    const actions = $('updateActions');

    content.innerHTML = '<p>正在下载更新...</p>';
    actions.innerHTML = '';

    try {
      const resp = await fetch('/api/do-update', { method: 'POST' });
      const data = await resp.json();

      if (data.error) {
        content.innerHTML = `<span style="color:var(--danger)">${data.error}</span>`;
        actions.innerHTML = '<button class="btn btn-outline" onclick="document.getElementById(\'updateOverlay\').classList.remove(\'active\')">关闭</button>';
        return;
      }

      content.innerHTML = `
        <p style="color:var(--success);margin-bottom:8px;">更新成功！</p>
        <p style="margin-bottom:4px;">提交: <code style="background:var(--bg-input);padding:2px 6px;border-radius:4px;font-size:11px;">${data.commit.substring(0, 7)}</code> — ${data.message}</p>
        <p style="margin-bottom:4px;">更新了 ${data.updatedFiles.length} 个文件</p>
        <p style="font-size:11px;color:var(--warning);margin-top:8px;">请刷新页面以加载最新版本</p>
      `;
      actions.innerHTML = `
        <button class="btn btn-outline" onclick="document.getElementById('updateOverlay').classList.remove('active')">稍后</button>
        <button class="btn btn-success" onclick="location.reload()">刷新页面</button>
      `;
      showToast('更新成功，请刷新页面', 'success');
    } catch (e) {
      content.innerHTML = `<span style="color:var(--danger)">更新失败: ${e.message}</span>`;
      actions.innerHTML = '<button class="btn btn-outline" onclick="document.getElementById(\'updateOverlay\').classList.remove(\'active\')">关闭</button>';
    }
  }

  // ========== 显示版本号 ==========
  fetch('/api/version').then(r => r.json()).then(data => {
    const tag = $('versionTag');
    if (tag) tag.textContent = 'v' + data.version;
  }).catch(() => {});

  // ========== 启动时自动检查更新（静默） ==========
  setTimeout(async () => {
    try {
      const resp = await fetch('/api/check-update');
      const data = await resp.json();
      if (data.hasUpdate) {
        showToast('发现新版本，点击顶部「检查更新」按钮更新', 'success');
      }
    } catch (e) { /* 静默失败 */ }
  }, 3000);

  // ========== 初始化 ==========
  writeConfigToUI();

  // iframe 加载完成后自动推送配置
  previewFrame.addEventListener('load', function () {
    setTimeout(updatePreview, 300);
  });

})();
