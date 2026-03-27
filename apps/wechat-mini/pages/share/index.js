const SHARE_PAYLOAD_STORAGE_KEY = "ec_share_payload";
const CANVAS_WIDTH = 720;
const CANVAS_HEIGHT = 1160;

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function clampText(value, maxLen) {
  const text = safeText(value);
  if (!text) return "";
  if (!maxLen || text.length <= maxLen) return text;
  return text.slice(0, maxLen);
}

function normalizeTriggerTags(value) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => safeText(item)).filter(Boolean).slice(0, 5);
}

function formatGeneratedAt(value) {
  const raw = safeText(value);
  if (!raw) return "";
  const dateObj = new Date(raw);
  if (Number.isNaN(dateObj.getTime())) return raw;
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  const dd = String(dateObj.getDate()).padStart(2, "0");
  const hh = String(dateObj.getHours()).padStart(2, "0");
  const mi = String(dateObj.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
}

function buildPayloadFromContext() {
  const app = getApp();
  const context = (app && app.globalData && app.globalData.latestAnalyzeContext) || {};
  const response = (context && context.response) || {};
  if (!response) return null;

  const resultCard = response.result_card || {};
  const primaryEmotion = resultCard.primary_emotion || response.emotion || {};
  const poem = response.poem || {};
  const guochao = response.guochao || {};

  const emotionLabel = safeText(primaryEmotion.label || primaryEmotion.code || "");
  const poemText = safeText(resultCard.poem_response || poem.text || "");
  const guochaoComfort = safeText(resultCard.guochao_comfort || guochao.comfort || "");
  if (!emotionLabel && !poemText && !guochaoComfort) {
    return null;
  }

  return {
    requestId: safeText(response.request_id),
    emotionLabel,
    emotionCode: safeText(primaryEmotion.code || ""),
    emotionOverview: clampText(resultCard.emotion_overview || "", 220),
    dailySuggestion: clampText(resultCard.daily_suggestion || "", 180),
    poet: safeText(poem.poet || "诗词回应"),
    poemText: clampText(poemText, 220),
    interpretation: clampText(resultCard.poem_interpretation || poem.interpretation || "", 180),
    guochaoName: safeText(guochao.name || "国潮伙伴"),
    comfort: clampText(guochaoComfort, 220),
    triggerTags: normalizeTriggerTags(resultCard.trigger_tags || []),
    checkedTodayText: "",
    currentStreak: 0,
    monthCheckinDays: 0,
    generatedAt: new Date().toISOString(),
  };
}

function normalizePayload(raw) {
  if (!raw || typeof raw !== "object") return null;
  const emotionLabel = safeText(raw.emotionLabel);
  const emotionOverview = clampText(raw.emotionOverview, 220);
  const poemText = clampText(raw.poemText, 220);
  const comfort = clampText(raw.comfort, 220);
  if (!emotionLabel && !emotionOverview && !poemText && !comfort) {
    return null;
  }
  return {
    requestId: safeText(raw.requestId),
    emotionLabel,
    emotionCode: safeText(raw.emotionCode),
    emotionOverview,
    dailySuggestion: clampText(raw.dailySuggestion, 180),
    poet: safeText(raw.poet || "诗词回应"),
    poemText,
    interpretation: clampText(raw.interpretation, 180),
    guochaoName: safeText(raw.guochaoName || "国潮伙伴"),
    comfort,
    triggerTags: normalizeTriggerTags(raw.triggerTags),
    checkedTodayText: safeText(raw.checkedTodayText),
    currentStreak: Number(raw.currentStreak) || 0,
    monthCheckinDays: Number(raw.monthCheckinDays) || 0,
    generatedAt: safeText(raw.generatedAt) || new Date().toISOString(),
  };
}

function wrapText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
  const content = safeText(text);
  if (!content) return y;

  let line = "";
  let drawY = y;
  let linesDrawn = 0;
  for (let i = 0; i < content.length; i += 1) {
    const char = content[i];
    const testLine = `${line}${char}`;
    const width = ctx.measureText(testLine).width;
    if (width > maxWidth && line) {
      ctx.fillText(line, x, drawY);
      line = char;
      drawY += lineHeight;
      linesDrawn += 1;
      if (maxLines > 0 && linesDrawn >= maxLines) {
        return drawY;
      }
    } else {
      line = testLine;
    }
  }
  if (line) {
    ctx.fillText(line, x, drawY);
    drawY += lineHeight;
  }
  return drawY;
}

function drawBlockTitle(ctx, title, y) {
  ctx.setFontSize(28);
  ctx.setFillStyle("#7a4f2c");
  ctx.fillText(title, 38, y);
  return y + 22;
}

Page({
  data: {
    hasData: false,
    payload: null,
    generatedAtText: "",
    isGenerating: false,
    imageTempPath: "",
    errorMsg: "",
    saveStatus: "",
    canvasWidth: CANVAS_WIDTH,
    canvasHeight: CANVAS_HEIGHT,
  },

  onLoad() {
    let payload = null;
    try {
      payload = normalizePayload(wx.getStorageSync(SHARE_PAYLOAD_STORAGE_KEY));
    } catch (err) {
      payload = null;
    }
    if (!payload) {
      payload = normalizePayload(buildPayloadFromContext());
    }

    if (!payload) {
      this.setData({
        hasData: false,
        errorMsg: "未找到可分享的结果，请先完成一次分析。",
      });
      return;
    }

    this.setData({
      hasData: true,
      payload,
      generatedAtText: formatGeneratedAt(payload.generatedAt),
      errorMsg: "",
    });
  },

  drawShareCardCanvas() {
    return new Promise((resolve) => {
      const payload = this.data.payload || {};
      const ctx = wx.createCanvasContext("shareCardCanvas", this);
      const width = CANVAS_WIDTH;
      const height = CANVAS_HEIGHT;

      ctx.setFillStyle("#f7f1e8");
      ctx.fillRect(0, 0, width, height);

      ctx.setFillStyle("#a1261b");
      ctx.fillRect(0, 0, width, 120);
      ctx.setFillStyle("#ffffff");
      ctx.setFontSize(34);
      ctx.fillText("情绪文化助手", 32, 72);

      ctx.setFillStyle("#fffaf1");
      ctx.fillRect(24, 140, width - 48, height - 180);
      ctx.setStrokeStyle("rgba(161, 38, 27, 0.15)");
      ctx.setLineWidth(2);
      ctx.strokeRect(24, 140, width - 48, height - 180);

      let y = 190;
      ctx.setFontSize(24);
      ctx.setFillStyle("#6f5a45");
      const emotionCodeText = safeText(payload.emotionCode);
      const codeText = emotionCodeText ? `（${emotionCodeText}）` : "";
      ctx.fillText(`主情绪：${safeText(payload.emotionLabel)}${codeText}`, 38, y);
      y += 42;

      const triggerTags = normalizeTriggerTags(payload.triggerTags);
      if (triggerTags.length) {
        ctx.setFontSize(22);
        ctx.setFillStyle("#7f6c58");
        ctx.fillText(`触发标签：${triggerTags.join("、")}`, 38, y);
        y += 36;
      }

      y = drawBlockTitle(ctx, "情绪概述", y + 14);
      ctx.setFontSize(24);
      ctx.setFillStyle("#3f2f22");
      y = wrapText(ctx, payload.emotionOverview || "暂无情绪概述。", 38, y + 16, width - 84, 34, 4);

      y = drawBlockTitle(ctx, "诗词回应", y + 16);
      ctx.setFontSize(22);
      ctx.setFillStyle("#7f6c58");
      ctx.fillText(safeText(payload.poet) || "诗词回应", 38, y + 14);
      y += 38;
      ctx.setFontSize(24);
      ctx.setFillStyle("#3f2f22");
      y = wrapText(ctx, payload.poemText || "暂无诗词内容。", 38, y + 12, width - 84, 34, 4);

      y = drawBlockTitle(ctx, "国潮慰藉", y + 10);
      ctx.setFontSize(22);
      ctx.setFillStyle("#7f6c58");
      ctx.fillText(safeText(payload.guochaoName) || "国潮伙伴", 38, y + 14);
      y += 38;
      ctx.setFontSize(24);
      ctx.setFillStyle("#3f2f22");
      y = wrapText(ctx, payload.comfort || "暂无慰藉内容。", 38, y + 12, width - 84, 34, 4);

      y = drawBlockTitle(ctx, "今日建议", y + 10);
      ctx.setFontSize(24);
      ctx.setFillStyle("#3f2f22");
      y = wrapText(ctx, payload.dailySuggestion || "保持稳定作息，照顾好自己。", 38, y + 16, width - 84, 34, 3);

      ctx.setFontSize(20);
      ctx.setFillStyle("#8f7f72");
      const footerY = Math.min(height - 56, y + 30);
      ctx.fillText(`生成时间：${formatGeneratedAt(payload.generatedAt)}`, 38, footerY);
      if (safeText(payload.requestId)) {
        ctx.fillText(`请求编号：${safeText(payload.requestId)}`, 38, footerY + 28);
      }

      ctx.draw(false, resolve);
    });
  },

  exportCanvasImage() {
    return new Promise((resolve, reject) => {
      wx.canvasToTempFilePath(
        {
          canvasId: "shareCardCanvas",
          x: 0,
          y: 0,
          width: CANVAS_WIDTH,
          height: CANVAS_HEIGHT,
          destWidth: CANVAS_WIDTH,
          destHeight: CANVAS_HEIGHT,
          fileType: "png",
          quality: 1,
          success: resolve,
          fail: reject,
        },
        this
      );
    });
  },

  async generateCard() {
    if (this.data.isGenerating || !this.data.hasData) return;
    this.setData({
      isGenerating: true,
      errorMsg: "",
      saveStatus: "",
    });
    wx.showLoading({ title: "生成卡片中..." });
    try {
      await this.drawShareCardCanvas();
      const exported = await this.exportCanvasImage();
      this.setData({
        imageTempPath: safeText(exported && exported.tempFilePath),
        saveStatus: "卡片已生成，可保存到相册。",
      });
      wx.showToast({ title: "生成成功", icon: "none" });
    } catch (err) {
      const message = safeText(err && err.errMsg) || safeText(err && err.message) || "卡片生成失败";
      this.setData({ errorMsg: message });
      wx.showToast({ title: "生成失败", icon: "none" });
    } finally {
      wx.hideLoading();
      this.setData({ isGenerating: false });
    }
  },

  async saveCardToAlbum() {
    let filePath = safeText(this.data.imageTempPath);
    if (!filePath) {
      await this.generateCard();
      filePath = safeText(this.data.imageTempPath);
    }
    if (!filePath) return;

    try {
      await new Promise((resolve, reject) => {
        wx.saveImageToPhotosAlbum({
          filePath,
          success: resolve,
          fail: reject,
        });
      });
      this.setData({ saveStatus: "已保存到相册。" });
      wx.showToast({ title: "保存成功", icon: "none" });
    } catch (err) {
      const message = safeText(err && err.errMsg) || "";
      if (message.includes("auth deny") || message.includes("authorize")) {
        wx.showModal({
          title: "需要相册权限",
          content: "请在设置中允许保存到相册后重试。",
          confirmText: "去设置",
          success(res) {
            if (res && res.confirm) {
              wx.openSetting();
            }
          },
        });
      }
      this.setData({ errorMsg: "保存失败，请检查相册权限后重试。" });
      wx.showToast({ title: "保存失败", icon: "none" });
    }
  },

  previewGeneratedCard() {
    const filePath = safeText(this.data.imageTempPath);
    if (!filePath) {
      wx.showToast({ title: "请先生成卡片", icon: "none" });
      return;
    }
    wx.previewImage({
      current: filePath,
      urls: [filePath],
    });
  },

  goBack() {
    wx.navigateBack({
      delta: 1,
      fail() {
        wx.reLaunch({ url: "/pages/index/index" });
      },
    });
  },

  onShareAppMessage() {
    const payload = this.data.payload || {};
    const emotionLabel = safeText(payload.emotionLabel) || "我的情绪复盘";
    return {
      title: `我的情绪复盘：${emotionLabel}`,
      path: "/pages/index/index",
    };
  },
});
