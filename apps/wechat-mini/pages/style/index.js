const { createMediaGenerateTask, getMediaGenerateTask, normalizeAssetUrl } = require("../../services/api");

const MEDIA_STYLE_CLASSICAL = "classical";
const MEDIA_STYLE_TECH = "tech";
const MEDIA_STYLE_GUOCHAO = "guochao";
const MEDIA_GENERATE_DEFAULT_POLL_MS = 2200;
const MEDIA_GENERATE_MAX_POLL_ATTEMPTS = 24;

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function pickResponse(context) {
  return (context && context.response) || {};
}

function pickResultCard(response) {
  return (response && response.result_card) || {};
}

function normalizeEmotionItem(item, fallbackCode) {
  const code = safeText((item && item.code) || fallbackCode);
  const label = safeText(item && item.label) || code || "未识别";
  return { code, label };
}

function normalizeTriggerTags(tags) {
  if (!Array.isArray(tags)) return [];

  const deduped = [];
  tags.forEach((tag) => {
    const normalized = safeText(tag);
    if (!normalized) return;
    if (!deduped.includes(normalized)) {
      deduped.push(normalized);
    }
  });
  return deduped.slice(0, 5);
}

function buildStylePageViewModel(response) {
  const resultCard = pickResultCard(response);
  const legacyEmotion = (response && response.emotion) || {};
  const primary = normalizeEmotionItem(resultCard.primary_emotion || legacyEmotion, legacyEmotion.code);
  return {
    requestId: safeText(response && response.request_id),
    emotionCode: primary.code,
    emotionLabel: primary.label,
    triggerTags: normalizeTriggerTags(resultCard.trigger_tags),
  };
}

function buildMediaGeneratePrompt(style, emotionLabel, triggerTags) {
  const mood = safeText(emotionLabel) || "当前情绪";
  const tags = Array.isArray(triggerTags)
    ? triggerTags.map((item) => safeText(item)).filter(Boolean).slice(0, 4)
    : [];
  const base =
    style === MEDIA_STYLE_CLASSICAL
      ? `古典风静态陪伴图片，主情绪：${mood}`
      : style === MEDIA_STYLE_TECH
        ? `科技风静态陪伴图片，主情绪：${mood}`
        : `国潮风静态陪伴图片，主情绪：${mood}`;
  return tags.length ? `${base}，关键词：${tags.join("、")}` : base;
}

function stableHash(input) {
  const text = safeText(input);
  let hash = 5381;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 33) ^ text.charCodeAt(i);
  }
  return (hash >>> 0).toString(16);
}

function buildMediaGenerateRequestToken(style, requestId) {
  const stamp = Date.now().toString(36);
  const styleText = safeText(style) || MEDIA_STYLE_CLASSICAL;
  const requestText = safeText(requestId) || "no_req";
  return `m4_${styleText}_${stableHash(`${requestText}_${stamp}`).slice(0, 12)}`;
}

function buildMediaGenerateStyleLabel(style) {
  if (style === MEDIA_STYLE_CLASSICAL) return "古典风";
  if (style === MEDIA_STYLE_GUOCHAO) return "国潮风";
  return "科技风";
}

function buildMediaGenerateStatusClass(status) {
  if (status === "succeeded") return "success";
  if (status === "failed") return "error";
  if (status === "queued" || status === "running" || status === "submitting") return "working";
  return "muted";
}

function buildMediaGenerateStatusText(task) {
  const status = safeText(task && task.status);
  const statusMessage = safeText(task && task.status_message);
  if (status === "queued") {
    return statusMessage || "任务已提交，正在排队。";
  }
  if (status === "running") {
    return statusMessage || "正在挑选风格图片，请稍候。";
  }
  if (status === "succeeded") {
    return "静态风格图已更新，可直接预览。";
  }
  return statusMessage || "";
}

function buildMediaGenerateFailureText(errorCode, detail, style) {
  const normalizedDetail = safeText(detail).toUpperCase();
  const normalizedErrorCode = safeText(errorCode).toUpperCase();
  const code = `${normalizedErrorCode} ${normalizedDetail}`.trim();
  if (code.includes("MEDIA_GEN_WEEKLY_LIMIT_EXCEEDED")) {
    return "本自然周风格图片次数已用完，当前继续使用静态配图。";
  }
  if (code.includes("MEDIA_GEN_POINTS_INSUFFICIENT")) {
    return "当前积分不足，当前继续使用静态配图。";
  }
  if (code.includes("MEDIA_GEN_PROVIDER_DISABLED")) {
    return "当前增强服务未开启，当前继续使用静态配图。";
  }
  if (code.includes("MEDIA_GEN_POOL_EMPTY") || code.includes("MEDIA_GEN_STATIC_POOL_EMPTY")) {
    if ((style || "") === MEDIA_STYLE_TECH) {
      return "科技风格图片暂未支持，请耐心等待后续发布。";
    }
    return "当前风格素材暂不可用，当前继续使用静态配图。";
  }
  if (code.includes("MEDIA_GEN_CONSENT_REQUIRED")) {
    return "授权未确认，本次未发起风格图片生成。";
  }
  if (code.includes("MEDIA_GEN_POLL_TIMEOUT")) {
    return "风格图片查询超时，当前继续使用静态配图，可稍后重试。";
  }
  const detailText = safeText(detail);
  if (detailText) {
    return `${detailText}；当前继续使用静态配图。`;
  }
  return "风格图片生成失败，当前继续使用静态配图，可稍后重试。";
}

Page({
  data: {
    hasData: false,
    requestId: "",
    emotionCode: "",
    emotionLabel: "",
    triggerTags: [],
    mediaGenerateStyle: MEDIA_STYLE_CLASSICAL,
    mediaGenerateStyleLabel: buildMediaGenerateStyleLabel(MEDIA_STYLE_CLASSICAL),
    mediaGenerateStatus: "",
    mediaGenerateStatusText: "点击任一风格按钮后，会直接开始切换图片。",
    mediaGenerateStatusClass: "muted",
    mediaGenerateTaskId: "",
    mediaGenerateLoading: false,
    mediaGenerateResultUrl: "",
    mediaGenerateResultStyle: "",
  },

  onLoad() {
    const app = getApp();
    const context = app.globalData.latestAnalyzeContext;
    const response = pickResponse(context);
    const viewModel = buildStylePageViewModel(response);

    if (!viewModel.requestId) {
      this.setData({ hasData: false });
      return;
    }

    const cached = app.globalData.latestMediaGenerateState || null;
    const cachedMatches = cached && safeText(cached.requestId) === viewModel.requestId;

    this.setData({
      hasData: true,
      requestId: viewModel.requestId,
      emotionCode: viewModel.emotionCode,
      emotionLabel: viewModel.emotionLabel,
      triggerTags: viewModel.triggerTags,
      mediaGenerateStyle: cachedMatches ? safeText(cached.mediaGenerateStyle) || MEDIA_STYLE_CLASSICAL : MEDIA_STYLE_CLASSICAL,
      mediaGenerateStyleLabel: buildMediaGenerateStyleLabel(
        cachedMatches ? safeText(cached.mediaGenerateStyle) || MEDIA_STYLE_CLASSICAL : MEDIA_STYLE_CLASSICAL
      ),
      mediaGenerateStatus: cachedMatches ? safeText(cached.mediaGenerateStatus) : "",
      mediaGenerateStatusText: cachedMatches
        ? safeText(cached.mediaGenerateStatusText) || "点击任一风格按钮后，会直接开始切换图片。"
        : "点击任一风格按钮后，会直接开始切换图片。",
      mediaGenerateStatusClass: cachedMatches
        ? buildMediaGenerateStatusClass(cached.mediaGenerateStatus)
        : "muted",
      mediaGenerateTaskId: cachedMatches ? safeText(cached.mediaGenerateTaskId) : "",
      mediaGenerateLoading: false,
      mediaGenerateResultUrl: cachedMatches ? safeText(cached.mediaGenerateResultUrl) : "",
      mediaGenerateResultStyle: cachedMatches ? safeText(cached.mediaGenerateResultStyle) : "",
    });
  },

  onUnload() {
    this.clearMediaGeneratePollTimer();
  },

  persistStyleState() {
    const app = getApp();
    app.globalData.latestMediaGenerateState = {
      requestId: this.data.requestId,
      mediaGenerateStyle: this.data.mediaGenerateStyle,
      mediaGenerateStatus: this.data.mediaGenerateStatus,
      mediaGenerateStatusText: this.data.mediaGenerateStatusText,
      mediaGenerateTaskId: this.data.mediaGenerateTaskId,
      mediaGenerateResultUrl: this.data.mediaGenerateResultUrl,
      mediaGenerateResultStyle: this.data.mediaGenerateResultStyle,
    };
  },

  applyMediaGenerateData(updates) {
    const merged = {
      mediaGenerateStyle: this.data.mediaGenerateStyle || MEDIA_STYLE_CLASSICAL,
      mediaGenerateStatus: this.data.mediaGenerateStatus || "",
      ...updates,
    };
    const style = safeText(merged.mediaGenerateStyle) || MEDIA_STYLE_CLASSICAL;
    merged.mediaGenerateStyle = style;
    merged.mediaGenerateStyleLabel = buildMediaGenerateStyleLabel(style);
    merged.mediaGenerateStatusClass = buildMediaGenerateStatusClass(merged.mediaGenerateStatus);
    this.setData(merged, () => this.persistStyleState());
  },

  clearMediaGeneratePollTimer() {
    if (this._mediaGeneratePollTimer) {
      clearTimeout(this._mediaGeneratePollTimer);
      this._mediaGeneratePollTimer = null;
    }
  },

  scheduleMediaGeneratePoll(taskId, delayMs, attempt) {
    this.clearMediaGeneratePollTimer();
    const nextDelay = Math.max(800, Number(delayMs) || MEDIA_GENERATE_DEFAULT_POLL_MS);
    this._mediaGeneratePollTimer = setTimeout(() => {
      this.pollMediaGenerateTask(taskId, attempt + 1);
    }, nextDelay);
  },

  applyMediaGenerateFailure(taskLike, fallbackMessage) {
    const style = safeText(taskLike && taskLike.style) || this.data.mediaGenerateStyle;
    const message =
      fallbackMessage ||
      buildMediaGenerateFailureText(taskLike && taskLike.error_code, taskLike && taskLike.message, style);
    this.applyMediaGenerateData({
      mediaGenerateStyle: style,
      mediaGenerateLoading: false,
      mediaGenerateStatus: "failed",
      mediaGenerateStatusText: message,
      mediaGenerateTaskId: safeText(taskLike && taskLike.task_id),
      mediaGenerateResultUrl: this.data.mediaGenerateResultUrl,
      mediaGenerateResultStyle: this.data.mediaGenerateResultStyle,
    });
  },

  async pollMediaGenerateTask(taskId, attempt) {
    if (!taskId) {
      this.applyMediaGenerateFailure({ style: this.data.mediaGenerateStyle }, "缺少任务编号");
      return;
    }

    if (attempt >= MEDIA_GENERATE_MAX_POLL_ATTEMPTS) {
      this.applyMediaGenerateFailure(
        { error_code: "MEDIA_GEN_POLL_TIMEOUT", style: this.data.mediaGenerateStyle },
        buildMediaGenerateFailureText("MEDIA_GEN_POLL_TIMEOUT", "", this.data.mediaGenerateStyle)
      );
      return;
    }

    try {
      const task = await getMediaGenerateTask(taskId);
      const status = safeText(task && task.status);
      const result = (task && task.result) || {};

      if (status === "succeeded") {
        const generatedImageUrl = normalizeAssetUrl(result.generated_image_url || result.image_url || "");
        this.applyMediaGenerateData({
          mediaGenerateTaskId: taskId,
          mediaGenerateLoading: false,
          mediaGenerateStatus: "succeeded",
          mediaGenerateStatusText: buildMediaGenerateStatusText(task),
          mediaGenerateResultUrl: generatedImageUrl,
          mediaGenerateResultStyle: safeText(result.style) || this.data.mediaGenerateStyle,
          mediaGenerateStyle: safeText(result.style) || this.data.mediaGenerateStyle,
        });
        return;
      }

      if (status === "failed") {
        this.applyMediaGenerateFailure(task, buildMediaGenerateFailureText(task.error_code, task.message, task.style));
        return;
      }

      this.applyMediaGenerateData({
        mediaGenerateTaskId: taskId,
        mediaGenerateLoading: true,
        mediaGenerateStatus: status || "running",
        mediaGenerateStatusText: buildMediaGenerateStatusText(task) || "结果查询中，正在继续刷新...",
      });
      this.scheduleMediaGeneratePoll(taskId, task && task.poll_after_ms, attempt);
    } catch (err) {
      this.applyMediaGenerateFailure(
        { error_code: "", message: (err && err.message) || "", style: this.data.mediaGenerateStyle },
        buildMediaGenerateFailureText("", (err && err.message) || "", this.data.mediaGenerateStyle)
      );
    }
  },

  async handleStyleTap(event) {
    const style = safeText(event && event.currentTarget && event.currentTarget.dataset.style);
    if (style !== MEDIA_STYLE_CLASSICAL && style !== MEDIA_STYLE_TECH && style !== MEDIA_STYLE_GUOCHAO) return;
    if (this.data.mediaGenerateLoading) return;

    try {
      const payload = {
        request_token: buildMediaGenerateRequestToken(style, this.data.requestId),
        analysis_request_id: this.data.requestId || undefined,
        style,
        emotion_code: this.data.emotionCode || undefined,
        emotion_label: this.data.emotionLabel || undefined,
        trigger_tags: Array.isArray(this.data.triggerTags) ? this.data.triggerTags.slice(0, 5) : [],
        prompt: buildMediaGeneratePrompt(style, this.data.emotionLabel, this.data.triggerTags),
        consent_confirmed: true,
      };

      this.applyMediaGenerateData({
        mediaGenerateStyle: style,
        mediaGenerateTaskId: "",
        mediaGenerateLoading: true,
        mediaGenerateStatus: "submitting",
        mediaGenerateStatusText: `正在切换到${buildMediaGenerateStyleLabel(style)}...`,
        mediaGenerateResultUrl: "",
        mediaGenerateResultStyle: "",
      });

      const task = await createMediaGenerateTask(payload);
      const taskId = safeText(task && task.task_id);
      if (!taskId) {
        throw new Error("未拿到风格图片任务编号");
      }

      this.applyMediaGenerateData({
        mediaGenerateStyle: style,
        mediaGenerateTaskId: taskId,
        mediaGenerateLoading: true,
        mediaGenerateStatus: safeText(task && task.status) || "queued",
        mediaGenerateStatusText: buildMediaGenerateStatusText(task),
      });
      this.scheduleMediaGeneratePoll(taskId, task && task.poll_after_ms, 0);
    } catch (err) {
      this.applyMediaGenerateFailure(
        { error_code: "", message: (err && err.message) || "", style },
        buildMediaGenerateFailureText("", (err && err.message) || "", style)
      );
      wx.showToast({
        title: "切换未发起",
        icon: "none",
      });
    }
  },
});
