const {
  createMediaGenerateTask,
  deleteFavoriteItem,
  getFavoriteStatus,
  getMediaGenerateTask,
  getRetentionCalendar,
  normalizeAssetUrl,
  sendEmail,
  upsertFavorite,
} = require("../../services/api");
const { uploadTempFile } = require("../../services/cloud");
const { requestAnalyzeWorkspaceReset } = require("../../utils/analyze-workspace");
const { ANALYZE_TAB, FAVORITES_TAB, HOME_TAB, JOURNEY_TAB } = require("../../utils/tabbar");

const DEFAULT_DAILY_SUGGESTION = "今天先做一件你能马上完成的小行动，逐步稳住状态。";
const FAVORITE_TYPE_POEM = "poem";
const FAVORITE_TYPE_GUOCHAO = "guochao";
const SHARE_PAYLOAD_STORAGE_KEY = "ec_share_payload";
const RESULT_IMAGE_RETRY_LIMIT = 2;
const MEDIA_STYLE_CLASSICAL = "classical";
const MEDIA_STYLE_TECH = "tech";
const MEDIA_STYLE_GUOCHAO = "guochao";
const MEDIA_GENERATE_DEFAULT_POLL_MS = 2200;
const MEDIA_GENERATE_MAX_POLL_ATTEMPTS = 24;

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeEmail(email) {
  return (email || "").trim();
}

function getEmailError(email) {
  if (!email) return "";
  if (email.length > 320) return "邮箱长度不能超过 320 个字符";
  const basicPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
  if (!basicPattern.test(email)) return "邮箱地址格式有误，请检查后重试";
  return "";
}

function pickRequest(context) {
  return (context && context.request) || {};
}

function pickResponse(context) {
  return (context && context.response) || {};
}

function hasResultPayload(response) {
  if (!response) return false;
  if (response.result_card) return true;
  if (response.emotion || response.poem || response.guochao) return true;
  return false;
}

function pickResultCard(response) {
  return (response && response.result_card) || {};
}

function pickSystemFields(response) {
  return (response && response.system_fields) || {};
}

function buildSpeechTranscriptHint(systemFields) {
  const status = safeText(systemFields && systemFields.speech_transcript_status);
  const error = safeText(systemFields && systemFields.speech_transcript_error);
  if (!status) return "";

  if (status === "provider_unconfigured") {
    return "这段录音已参与分析，暂未生成可阅读文字。";
  }
  if (status === "service_disabled") {
    return "这段录音已参与分析，当前暂不展示转写文字。";
  }
  if (status === "request_failed" || status === "runtime_error") {
    return "这段录音已参与分析，但文字整理失败了。";
  }
  if (status.indexOf("rejected:") === 0) {
    return error ? `录音已参与分析，但文字整理未通过：${error}` : "录音已参与分析，但暂未整理出清晰文字。";
  }
  if (status === "empty") {
    return "录音已参与分析，但暂未识别出清晰文字。";
  }
  if (status === "ok") {
    return "";
  }
  return "录音已参与分析，暂未展示转写文字。";
}

function pickProcessingMetrics(systemFields) {
  const raw = systemFields && systemFields.processing_metrics_ms;
  if (!raw || typeof raw !== "object") return {};
  const normalized = {};
  Object.keys(raw).forEach((key) => {
    const value = Number(raw[key]);
    if (Number.isFinite(value) && value >= 0) {
      normalized[key] = Math.round(value);
    }
  });
  return normalized;
}

function buildProcessingSummary(metrics) {
  if (!metrics || typeof metrics !== "object") return "";
  const total = Number(metrics.total_ms);
  if (!Number.isFinite(total) || total <= 0) return "";

  const parts = [];
  if (Number(metrics.resolve_media_ms) > 0) {
    parts.push(`下载${Math.round(metrics.resolve_media_ms)}ms`);
  }
  if (Number(metrics.asr_transcribe_ms) > 0) {
    parts.push(`转写${Math.round(metrics.asr_transcribe_ms)}ms`);
  }
  if (Number(metrics.face_emotion_ms) > 0) {
    parts.push(`人脸${Math.round(metrics.face_emotion_ms)}ms`);
  }
  if (Number(metrics.voice_emotion_ms) > 0) {
    parts.push(`语音情绪${Math.round(metrics.voice_emotion_ms)}ms`);
  }
  return parts.length ? `服务耗时：总 ${Math.round(total)}ms（${parts.join("，")}）` : `服务耗时：总 ${Math.round(total)}ms`;
}

function normalizeEmotionItem(item, fallbackCode) {
  const code = safeText((item && item.code) || fallbackCode);
  const label = safeText(item && item.label) || code || "未识别";
  return { code, label };
}

function normalizeSecondaryEmotions(items) {
  if (!Array.isArray(items)) return [];

  const deduped = [];
  items.forEach((item) => {
    const rawCode = safeText(item && item.code);
    const rawLabel = safeText(item && item.label);
    if (!rawCode && !rawLabel) return;

    const normalized = normalizeEmotionItem(item);
    const key = `${normalized.code}|${normalized.label}`;
    if (!deduped.some((existing) => `${existing.code}|${existing.label}` === key)) {
      deduped.push(normalized);
    }
  });
  return deduped.slice(0, 3);
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

function buildLegacyOverview(primaryLabel) {
  if (!primaryLabel) {
    return "暂未生成情绪概述，请结合主情绪理解当前状态。";
  }
  return `当前以“${primaryLabel}”为主，建议结合下方内容进一步理解。`;
}

function buildResultHeroTheme(emotionCode) {
  const code = safeText(emotionCode).toLowerCase();
  if (code === "happy") return "happy";
  if (code === "sad") return "sad";
  if (code === "angry") return "angry";
  if (code === "surprise") return "surprise";
  if (code === "fear") return "fear";
  if (code === "neutral") return "neutral";
  return "neutral";
}

function buildResultHeroTone(emotionCode, emotionLabel) {
  const label = safeText(emotionLabel) || "待识别";
  const code = buildResultHeroTheme(emotionCode);
  if (code === "happy") return `偏暖 · ${label}`;
  if (code === "sad") return `轻缓 · ${label}`;
  if (code === "angry") return `收束 · ${label}`;
  if (code === "surprise") return `展开 · ${label}`;
  if (code === "fear") return `安定 · ${label}`;
  return `平衡 · ${label}`;
}

function mapInputModeLabel(mode) {
  if (mode === "text") return "文字";
  if (mode === "voice") return "录音";
  if (mode === "selfie") return "自拍";
  return safeText(mode) || "输入";
}

function buildResultViewModel(response) {
  const resultCard = pickResultCard(response);
  const systemFields = pickSystemFields(response);
  const legacyEmotion = (response && response.emotion) || {};
  const legacyPoem = (response && response.poem) || {};
  const legacyGuochao = (response && response.guochao) || {};
  const speechTranscript = safeText(systemFields.speech_transcript);
  const processingMetrics = pickProcessingMetrics(systemFields);

  const primary = normalizeEmotionItem(resultCard.primary_emotion || legacyEmotion, legacyEmotion.code);
  const secondary = normalizeSecondaryEmotions(resultCard.secondary_emotions);
  const triggerTags = normalizeTriggerTags(resultCard.trigger_tags);

  return {
    requestId: safeText(response && response.request_id),
    emotionCode: primary.code,
    emotionLabel: primary.label,
    secondaryEmotions: secondary,
    emotionOverview: safeText(resultCard.emotion_overview) || buildLegacyOverview(primary.label),
    triggerTags,
    dailySuggestion: safeText(resultCard.daily_suggestion) || DEFAULT_DAILY_SUGGESTION,
    poet: safeText(legacyPoem.poet) || "诗词回应",
    poemText: safeText(resultCard.poem_response) || safeText(legacyPoem.text) || "暂未生成诗词回应。",
    interpretation:
      safeText(resultCard.poem_interpretation) || safeText(legacyPoem.interpretation) || "暂未生成诗词解读。",
    guochaoName: safeText(legacyGuochao.name) || "国潮伙伴",
    comfort: safeText(resultCard.guochao_comfort) || safeText(legacyGuochao.comfort) || "暂未生成国潮慰藉内容。",
    speechTranscript,
    speechTranscriptHint: speechTranscript ? "" : buildSpeechTranscriptHint(systemFields),
    processingMetrics,
    processingSummary: buildProcessingSummary(processingMetrics),
  };
}

function pickUserImageFileId(req) {
  return req.imageFileId || req.image_file_id || req.userImageFileId || req.user_image_file_id || "";
}

function pickUserImageUrl(req) {
  return req.imageTempUrl || req.image_url || req.userImageUrl || req.user_image_url || "";
}

function pickUserImageTempPath(req) {
  return req.imageTempPath || req.image_temp_path || "";
}

function pickUserAudioFileId(req) {
  return (
    req.audioFileId ||
    req.audio_file_id ||
    req.userAudioFileId ||
    req.user_audio_file_id ||
    req.uploadedAudioFileId ||
    req.uploaded_audio_file_id ||
    ""
  );
}

function pickUserAudioUrl(req) {
  return (
    req.audioTempUrl ||
    req.audio_url ||
    req.userAudioUrl ||
    req.user_audio_url ||
    req.uploadedAudioTempUrl ||
    req.uploaded_audio_url ||
    ""
  );
}

function pickUserAudioTempPath(req) {
  return (
    req.audioTempPath ||
    req.audio_temp_path ||
    req.userAudioTempPath ||
    req.user_audio_temp_path ||
    req.uploadedAudioTempPath ||
    req.uploaded_audio_temp_path ||
    ""
  );
}

function clearRequestUserImageRefs(req) {
  if (!req) return;
  req.imageFileId = "";
  req.image_file_id = "";
  req.userImageFileId = "";
  req.user_image_file_id = "";

  req.imageTempUrl = "";
  req.image_url = "";
  req.userImageUrl = "";
  req.user_image_url = "";

  req.imageTempPath = "";
  req.image_temp_path = "";
  req.userImageTempPath = "";
  req.user_image_temp_path = "";
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

function buildMediaGenerateRequestToken(style, requestId) {
  const stamp = Date.now().toString(36);
  const styleText = safeText(style) || MEDIA_STYLE_CLASSICAL;
  const requestText = safeText(requestId) || "no_req";
  return `m3_${styleText}_${stableHash(`${requestText}_${stamp}`).slice(0, 12)}`;
}

function buildMediaGenerateStyleLabel(style) {
  if (style === MEDIA_STYLE_CLASSICAL) return "古典风";
  if (style === MEDIA_STYLE_GUOCHAO) return "国潮风";
  return "科技风";
}

function buildMediaGenerateActionText(status, loading) {
  if (loading) return "切换中...";
  if (status === "succeeded") return "重新切换风格图";
  if (status === "failed") return "重试风格图";
  return "切换风格图";
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

function normalizeMonthValue(value) {
  const dateObj = value ? new Date(value) : new Date();
  const safeDate = Number.isNaN(dateObj.getTime()) ? new Date() : dateObj;
  const yyyy = safeDate.getFullYear();
  const mm = String(safeDate.getMonth() + 1).padStart(2, "0");
  return `${yyyy}-${mm}`;
}

function stableHash(input) {
  const text = safeText(input);
  let hash = 5381;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 33) ^ text.charCodeAt(i);
  }
  return (hash >>> 0).toString(16);
}

function clampText(value, maxLen) {
  const text = safeText(value);
  if (!text) return "";
  if (!maxLen || text.length <= maxLen) return text;
  return text.slice(0, maxLen);
}

function buildFavoriteTargetId(type, parts) {
  const normalizedType = safeText(type) || "item";
  const raw = Array.isArray(parts) ? parts.map(safeText).join("|") : safeText(parts);
  const hash = stableHash(raw || `${normalizedType}_${Date.now()}`);
  return `${normalizedType}_${hash.slice(0, 12)}`;
}

function parseFavoriteFlag(result) {
  if (!result || typeof result !== "object") return false;
  if (result.is_favorited === true) return true;
  if (result.isFavorite === true) return true;
  if (result.is_favorite === true) return true;
  return false;
}

function extractErrorMessage(err, fallback) {
  return ((err && err.message) || fallback || "").trim();
}

function isFavoriteDisabledError(message) {
  return typeof message === "string" && message.includes("RETENTION_FAVORITES_DISABLED");
}

function buildSharePayloadFromData(data) {
  const triggerTags = Array.isArray(data && data.triggerTags) ? data.triggerTags : [];
  const userImageUrl =
    data && data.userImageRemoved
      ? ""
      : safeText(data && data.userImagePreviewUrl);
  return {
    requestId: safeText(data && data.requestId),
    emotionLabel: safeText(data && data.emotionLabel),
    emotionCode: safeText(data && data.emotionCode),
    emotionOverview: clampText(data && data.emotionOverview, 220),
    dailySuggestion: clampText(data && data.dailySuggestion, 180),
    poet: safeText(data && data.poet),
    poemText: clampText(data && data.poemText, 220),
    interpretation: clampText(data && data.interpretation, 180),
    guochaoName: safeText(data && data.guochaoName),
    comfort: clampText(data && data.comfort, 220),
    triggerTags: triggerTags.slice(0, 5),
    userImageUrl,
    checkedTodayText: safeText(data && data.checkedTodayText),
    currentStreak: Number(data && data.currentStreak) || 0,
    monthCheckinDays: Number(data && data.monthCheckinDays) || 0,
    generatedAt: new Date().toISOString(),
  };
}

Page({
  data: {
    hasData: false,
    requestId: "",
    processingSummary: "",
    emotionCode: "",
    emotionLabel: "",
    resultHeroTheme: "neutral",
    resultHeroTone: "平衡 · 待识别",
    secondaryEmotions: [],
    emotionOverview: "",
    triggerTags: [],
    dailySuggestion: "",
    poet: "",
    poemText: "",
    interpretation: "",
    guochaoName: "",
    comfort: "",
    speechTranscript: "",
    speechTranscriptHint: "",
    poetImageUrl: "",
    guochaoImageUrl: "",
    poetImageFailed: false,
    guochaoImageFailed: false,
    poetImageLoading: false,
    guochaoImageLoading: false,
    poetImageErrorRetries: 0,
    guochaoImageErrorRetries: 0,
    userImagePreviewUrl: "",
    userImageVisible: false,
    userImageFailed: false,
    userImageRemoved: false,
    mediaGenerateAvailable: false,
    mediaGenerateStyle: MEDIA_STYLE_CLASSICAL,
    mediaGenerateStyleLabel: buildMediaGenerateStyleLabel(MEDIA_STYLE_CLASSICAL),
    mediaGenerateActionText: buildMediaGenerateActionText("", false),
    mediaGenerateStatus: "",
    mediaGenerateStatusText: "",
    mediaGenerateStatusClass: "muted",
    mediaGenerateTaskId: "",
    mediaGenerateLoading: false,
    mediaGenerateRetryable: false,
    mediaGenerateError: "",
    mediaGenerateResultUrl: "",
    mediaGenerateResultStyle: "",
    email: "",
    emailError: "",
    emailSheetVisible: false,
    emailFocused: false,
    keyboardHeight: 0,
    actionBarBottomPx: 0,
    bottomPaddingPx: 364,
    isSendingEmail: false,
    emailStatus: "",
    emailStatusClass: "",
    retentionLoading: false,
    retentionErrorMsg: "",
    checkedToday: false,
    checkedTodayText: "今日未打卡",
    checkedTodayClass: "miss",
    currentStreak: 0,
    longestStreak: 0,
    monthCheckinDays: 0,
    favoriteErrorMsg: "",
    poemFavoriteTargetId: "",
    poemFavoriteId: "",
    poemFavorited: false,
    poemFavoriteLoading: false,
    poemFavoriteButtonText: "收藏诗词",
    poemFavoriteBadgeText: "",
    guochaoFavoriteTargetId: "",
    guochaoFavoriteId: "",
    guochaoFavorited: false,
    guochaoFavoriteLoading: false,
    guochaoFavoriteButtonText: "收藏国潮",
    guochaoFavoriteBadgeText: "",
    requestTextPreview: "",
    inputModeBadges: [],
  },

  onLoad() {
    const app = getApp();
    const context = app.globalData.latestAnalyzeContext;
    const response = pickResponse(context);

    if (!hasResultPayload(response)) {
      this.setData({ hasData: false });
      return;
    }

    this._analysisContext = context;
    const request = pickRequest(context);
    const userImagePreviewUrl = pickUserImageUrl(request) || pickUserImageTempPath(request);
    const viewModel = buildResultViewModel(response);
    const poemFavoriteTargetId = buildFavoriteTargetId(FAVORITE_TYPE_POEM, [
      viewModel.poet,
      viewModel.poemText,
      viewModel.interpretation,
    ]);
    const guochaoFavoriteTargetId = buildFavoriteTargetId(FAVORITE_TYPE_GUOCHAO, [
      viewModel.guochaoName,
      viewModel.comfort,
      viewModel.dailySuggestion,
    ]);

    const poetImageUrl = normalizeAssetUrl(response.poet_image_url || "");
    const guochaoImageUrl = normalizeAssetUrl(response.guochao_image_url || "");

    this.setData({
      hasData: true,
      requestId: viewModel.requestId,
      processingSummary: viewModel.processingSummary,
      emotionCode: viewModel.emotionCode,
      emotionLabel: viewModel.emotionLabel,
      resultHeroTheme: buildResultHeroTheme(viewModel.emotionCode),
      resultHeroTone: buildResultHeroTone(viewModel.emotionCode, viewModel.emotionLabel),
      secondaryEmotions: viewModel.secondaryEmotions,
      emotionOverview: viewModel.emotionOverview,
      triggerTags: viewModel.triggerTags,
      dailySuggestion: viewModel.dailySuggestion,
      poet: viewModel.poet,
      poemText: viewModel.poemText,
      interpretation: viewModel.interpretation,
      guochaoName: viewModel.guochaoName,
      comfort: viewModel.comfort,
      speechTranscript: viewModel.speechTranscript,
      speechTranscriptHint: viewModel.speechTranscriptHint,
      poetImageUrl,
      guochaoImageUrl,
      poetImageFailed: false,
      guochaoImageFailed: false,
      poetImageLoading: !!poetImageUrl,
      guochaoImageLoading: !!guochaoImageUrl,
      poetImageErrorRetries: 0,
      guochaoImageErrorRetries: 0,
      userImagePreviewUrl,
      userImageVisible: !!userImagePreviewUrl,
      userImageFailed: false,
      userImageRemoved: false,
      mediaGenerateAvailable: true,
      mediaGenerateStyle: MEDIA_STYLE_CLASSICAL,
      mediaGenerateStyleLabel: buildMediaGenerateStyleLabel(MEDIA_STYLE_CLASSICAL),
      mediaGenerateActionText: buildMediaGenerateActionText("", false),
      mediaGenerateStatus: "",
      mediaGenerateStatusText: "选择风格后，点击按钮即可换一张静态风格图；失败时不影响当前静态结果和邮件。",
      mediaGenerateStatusClass: "muted",
      mediaGenerateTaskId: "",
      mediaGenerateLoading: false,
      mediaGenerateRetryable: false,
      mediaGenerateError: "",
      mediaGenerateResultUrl: "",
      mediaGenerateResultStyle: "",
      emailSheetVisible: false,
      favoriteErrorMsg: "",
      poemFavoriteTargetId,
      poemFavoriteId: "",
      poemFavorited: false,
      poemFavoriteLoading: false,
      poemFavoriteButtonText: "收藏诗词",
      poemFavoriteBadgeText: "",
      guochaoFavoriteTargetId,
      guochaoFavoriteId: "",
      guochaoFavorited: false,
      guochaoFavoriteLoading: false,
      guochaoFavoriteButtonText: "收藏国潮",
      guochaoFavoriteBadgeText: "",
      requestTextPreview: safeText(request.text),
      inputModeBadges: Array.isArray(request.input_modes) ? request.input_modes.map(mapInputModeLabel) : [],
    });
    this.refreshRetentionSnapshot();
    this.refreshFavoriteStatus();

    if (wx.onKeyboardHeightChange) {
      this._keyboardHandler = (res) => {
        const height = Math.max(0, (res && res.height) || 0);
        this.setData(
          {
            keyboardHeight: height,
            actionBarBottomPx: height > 0 ? height : 0,
            bottomPaddingPx: height > 0 ? height + 424 : 364,
          }
        );
      };
      wx.onKeyboardHeightChange(this._keyboardHandler);
    }
  },

  applyMediaGenerateData(updates) {
    const merged = {
      mediaGenerateStyle: this.data.mediaGenerateStyle || MEDIA_STYLE_CLASSICAL,
      mediaGenerateStatus: this.data.mediaGenerateStatus || "",
      mediaGenerateLoading: !!this.data.mediaGenerateLoading,
      ...updates,
    };
    const style = safeText(merged.mediaGenerateStyle) || MEDIA_STYLE_CLASSICAL;
    const status = safeText(merged.mediaGenerateStatus);
    const loading = !!merged.mediaGenerateLoading;
    merged.mediaGenerateStyle = style;
    merged.mediaGenerateStyleLabel = buildMediaGenerateStyleLabel(style);
    merged.mediaGenerateActionText = buildMediaGenerateActionText(status, loading);
    merged.mediaGenerateStatusClass = buildMediaGenerateStatusClass(status);
    this.setData(merged);
  },

  clearMediaGeneratePollTimer() {
    if (this._mediaGeneratePollTimer) {
      clearTimeout(this._mediaGeneratePollTimer);
      this._mediaGeneratePollTimer = null;
    }
  },

  scheduleMediaGeneratePoll(taskId, delayMs, attempt) {
    this.clearMediaGeneratePollTimer();
    const waitMs = Math.max(400, Number(delayMs) || MEDIA_GENERATE_DEFAULT_POLL_MS);
    this._mediaGeneratePollTimer = setTimeout(() => {
      this.pollMediaGenerateTask(taskId, attempt);
    }, waitMs);
  },

  applyMediaGenerateFailure(taskLike, fallbackText) {
    const errorCode = safeText(taskLike && taskLike.error_code);
    const detail = safeText(taskLike && (taskLike.error_detail || taskLike.message));
    const style = safeText(taskLike && taskLike.style) || this.data.mediaGenerateStyle;
    const message = fallbackText || buildMediaGenerateFailureText(errorCode, detail, style);
    this.clearMediaGeneratePollTimer();
    this.applyMediaGenerateData({
      mediaGenerateLoading: false,
      mediaGenerateStatus: "failed",
      mediaGenerateStatusText: message,
      mediaGenerateRetryable: !!(taskLike && taskLike.retryable),
      mediaGenerateError: message,
      mediaGenerateResultUrl: "",
      mediaGenerateResultStyle: "",
    });
  },

  async pollMediaGenerateTask(taskId, attempt = 0) {
    if (!taskId) return;
    try {
      const task = await getMediaGenerateTask(taskId);
      const status = safeText(task && task.status);
      if (status === "queued" || status === "running") {
        if (attempt >= MEDIA_GENERATE_MAX_POLL_ATTEMPTS) {
          this.applyMediaGenerateFailure(
            { error_code: "MEDIA_GEN_POLL_TIMEOUT", retryable: true, style: this.data.mediaGenerateStyle },
            buildMediaGenerateFailureText("MEDIA_GEN_POLL_TIMEOUT", "", this.data.mediaGenerateStyle)
          );
          return;
        }
        this.applyMediaGenerateData({
          mediaGenerateTaskId: taskId,
          mediaGenerateLoading: true,
          mediaGenerateStatus: status,
          mediaGenerateStatusText: buildMediaGenerateStatusText(task),
          mediaGenerateRetryable: false,
          mediaGenerateError: "",
        });
        this.scheduleMediaGeneratePoll(taskId, task && task.poll_after_ms, attempt + 1);
        return;
      }

      if (status === "succeeded") {
        const result = (task && task.result) || {};
        const generatedImageUrl = normalizeAssetUrl(result.generated_image_url || "");
        if (!generatedImageUrl) {
          this.applyMediaGenerateFailure(
            {
              error_code: "MEDIA_GEN_BAD_RESULT",
              error_detail: "结果缺少可显示图片地址",
              retryable: true,
              style: safeText(result.style) || this.data.mediaGenerateStyle,
            },
            "风格图片已生成，但预览地址缺失，当前继续使用静态配图。"
          );
          return;
        }
        this.clearMediaGeneratePollTimer();
        this.applyMediaGenerateData({
          mediaGenerateTaskId: taskId,
          mediaGenerateLoading: false,
          mediaGenerateStatus: "succeeded",
          mediaGenerateStatusText: buildMediaGenerateStatusText(task),
          mediaGenerateRetryable: false,
          mediaGenerateError: "",
          mediaGenerateResultUrl: generatedImageUrl,
          mediaGenerateResultStyle: safeText(result.style) || this.data.mediaGenerateStyle,
        });
        return;
      }

      if (status === "failed") {
        this.applyMediaGenerateFailure(task);
        return;
      }

      if (attempt >= MEDIA_GENERATE_MAX_POLL_ATTEMPTS) {
        this.applyMediaGenerateFailure(
          { error_code: "MEDIA_GEN_POLL_TIMEOUT", retryable: true, style: this.data.mediaGenerateStyle },
          buildMediaGenerateFailureText("MEDIA_GEN_POLL_TIMEOUT", "", this.data.mediaGenerateStyle)
        );
        return;
      }
      this.applyMediaGenerateData({
        mediaGenerateTaskId: taskId,
        mediaGenerateLoading: true,
        mediaGenerateStatus: "running",
        mediaGenerateStatusText: "结果查询中，正在继续刷新...",
        mediaGenerateRetryable: false,
      });
      this.scheduleMediaGeneratePoll(taskId, MEDIA_GENERATE_DEFAULT_POLL_MS, attempt + 1);
    } catch (err) {
      if (attempt >= MEDIA_GENERATE_MAX_POLL_ATTEMPTS) {
        this.applyMediaGenerateFailure(
          {
            error_code: "MEDIA_GEN_POLL_TIMEOUT",
            message: (err && err.message) || "",
            style: this.data.mediaGenerateStyle,
          },
          buildMediaGenerateFailureText("MEDIA_GEN_POLL_TIMEOUT", "", this.data.mediaGenerateStyle)
        );
        return;
      }
      this.applyMediaGenerateData({
        mediaGenerateTaskId: taskId,
        mediaGenerateLoading: true,
        mediaGenerateStatus: "running",
        mediaGenerateStatusText: "结果查询中断，正在自动重试...",
        mediaGenerateRetryable: true,
      });
      this.scheduleMediaGeneratePoll(taskId, 1200, attempt + 1);
    }
  },

  appendImageRetryToken(url, retryIndex) {
    const raw = safeText(url);
    if (!raw) return "";
    const stamp = `${Date.now()}_${retryIndex}`;
    const joiner = raw.includes("?") ? "&" : "?";
    return `${raw}${joiner}ec_retry=${stamp}`;
  },

  retryImageByField(fieldPrefix, event) {
    const urlKey = `${fieldPrefix}ImageUrl`;
    const failedKey = `${fieldPrefix}ImageFailed`;
    const loadingKey = `${fieldPrefix}ImageLoading`;
    const retriesKey = `${fieldPrefix}ImageErrorRetries`;
    const currentUrl = safeText(this.data[urlKey]);
    const retries = Number(this.data[retriesKey]) || 0;

    if (!currentUrl) {
      this.setData({
        [loadingKey]: false,
        [failedKey]: true,
      });
      return;
    }

    if (retries < RESULT_IMAGE_RETRY_LIMIT) {
      this.setData({
        [urlKey]: this.appendImageRetryToken(currentUrl, retries + 1),
        [retriesKey]: retries + 1,
        [failedKey]: false,
        [loadingKey]: true,
      });
      return;
    }

    console.warn(`${fieldPrefix} image load failed`, (event && event.detail && event.detail.errMsg) || "");
    this.setData({
      [failedKey]: true,
      [loadingKey]: false,
    });
  },

  async refreshRetentionSnapshot() {
    const context = this._analysisContext || {};
    const response = pickResponse(context);
    const systemFields = pickSystemFields(response);
    const analyzedAt = safeText(systemFields.analyzed_at);
    const month = normalizeMonthValue(analyzedAt);

    this.setData({
      retentionLoading: true,
      retentionErrorMsg: "",
    });

    try {
      const retention = await getRetentionCalendar(month);
      const checkedToday = !!(retention && retention.checked_today);
      this.setData({
        checkedToday,
        checkedTodayText: checkedToday ? "今日已打卡" : "今日未打卡",
        checkedTodayClass: checkedToday ? "ok" : "miss",
        currentStreak: Number(retention && retention.current_streak) || 0,
        longestStreak: Number(retention && retention.longest_streak) || 0,
        monthCheckinDays: Number(retention && retention.checked_days) || 0,
      });
    } catch (err) {
      this.setData({
        retentionErrorMsg: "记录状态稍后刷新，不影响查看本次结果。",
      });
    } finally {
      this.setData({ retentionLoading: false });
    }
  },

  syncFavoriteButtonTexts() {
    this.setData({
      poemFavoriteButtonText: this.data.poemFavorited ? "取消收藏诗词" : "收藏诗词",
      poemFavoriteBadgeText: this.data.poemFavorited ? "已收藏" : "",
      guochaoFavoriteButtonText: this.data.guochaoFavorited ? "取消收藏国潮" : "收藏国潮",
      guochaoFavoriteBadgeText: this.data.guochaoFavorited ? "已收藏" : "",
    });
  },

  async refreshFavoriteStatus() {
    const poemTargetId = safeText(this.data.poemFavoriteTargetId);
    const guochaoTargetId = safeText(this.data.guochaoFavoriteTargetId);
    if (!poemTargetId && !guochaoTargetId) return;

    this.setData({
      favoriteErrorMsg: "",
      poemFavoriteLoading: !!poemTargetId,
      guochaoFavoriteLoading: !!guochaoTargetId,
    });

    const updates = {};
    try {
      const tasks = [];
      if (poemTargetId) {
        tasks.push(
          getFavoriteStatus({ favoriteType: FAVORITE_TYPE_POEM, targetId: poemTargetId }).then((res) => ({
            type: FAVORITE_TYPE_POEM,
            res,
          }))
        );
      }
      if (guochaoTargetId) {
        tasks.push(
          getFavoriteStatus({ favoriteType: FAVORITE_TYPE_GUOCHAO, targetId: guochaoTargetId }).then((res) => ({
            type: FAVORITE_TYPE_GUOCHAO,
            res,
          }))
        );
      }

      const statusItems = await Promise.all(tasks);
      statusItems.forEach((item) => {
        const favorited = parseFavoriteFlag(item.res);
        const favoriteId = safeText(item && item.res && item.res.item && item.res.item.favorite_id);
        if (item.type === FAVORITE_TYPE_POEM) {
          updates.poemFavorited = favorited;
          updates.poemFavoriteId = favoriteId;
        } else if (item.type === FAVORITE_TYPE_GUOCHAO) {
          updates.guochaoFavorited = favorited;
          updates.guochaoFavoriteId = favoriteId;
        }
      });
    } catch (err) {
      const message = extractErrorMessage(err, "收藏状态加载失败");
      updates.favoriteErrorMsg = isFavoriteDisabledError(message)
        ? "收藏功能未开启，当前仅可浏览结果。"
        : message;
    } finally {
      updates.poemFavoriteLoading = false;
      updates.guochaoFavoriteLoading = false;
      this.setData(updates, () => this.syncFavoriteButtonTexts());
    }
  },

  buildFavoritePayload(type) {
    const isPoem = type === FAVORITE_TYPE_POEM;
    if (isPoem) {
      return {
        favorite_type: FAVORITE_TYPE_POEM,
        target_id: this.data.poemFavoriteTargetId,
        title: clampText(this.data.poemText || "诗词回应", 500),
        subtitle: clampText(this.data.poet || "诗词回应", 200),
        content_summary: clampText(this.data.interpretation || this.data.emotionOverview || "", 800),
        request_id: this.data.requestId || undefined,
        metadata: {
          emotion_code: this.data.emotionCode || "",
          emotion_label: this.data.emotionLabel || "",
        },
      };
    }
    return {
      favorite_type: FAVORITE_TYPE_GUOCHAO,
      target_id: this.data.guochaoFavoriteTargetId,
      title: clampText(this.data.guochaoName || "国潮伙伴慰藉", 500),
      subtitle: clampText(this.data.emotionLabel || "情绪陪伴", 200),
      content_summary: clampText(this.data.comfort || this.data.dailySuggestion || "", 800),
      request_id: this.data.requestId || undefined,
      metadata: {
        emotion_code: this.data.emotionCode || "",
        emotion_label: this.data.emotionLabel || "",
      },
    };
  },

  async toggleFavorite(type) {
    const isPoem = type === FAVORITE_TYPE_POEM;
    const loadingKey = isPoem ? "poemFavoriteLoading" : "guochaoFavoriteLoading";
    const favoritedKey = isPoem ? "poemFavorited" : "guochaoFavorited";
    const favoriteIdKey = isPoem ? "poemFavoriteId" : "guochaoFavoriteId";
    const targetIdKey = isPoem ? "poemFavoriteTargetId" : "guochaoFavoriteTargetId";

    if (this.data[loadingKey]) return;
    const targetId = safeText(this.data[targetIdKey]);
    if (!targetId) return;

    this.setData({
      [loadingKey]: true,
      favoriteErrorMsg: "",
    });

    try {
      if (this.data[favoritedKey]) {
        let favoriteId = safeText(this.data[favoriteIdKey]);
        if (!favoriteId) {
          const statusRes = await getFavoriteStatus({ favoriteType: type, targetId });
          favoriteId = safeText(statusRes && statusRes.item && statusRes.item.favorite_id);
        }
        if (favoriteId) {
          await deleteFavoriteItem(favoriteId);
        }
        this.setData({
          [favoritedKey]: false,
          [favoriteIdKey]: "",
        });
        wx.showToast({ title: "已取消收藏", icon: "none" });
      } else {
        const payload = this.buildFavoritePayload(type);
        const result = await upsertFavorite(payload);
        const favoriteId = safeText(result && result.item && result.item.favorite_id);
        this.setData({
          [favoritedKey]: true,
          [favoriteIdKey]: favoriteId,
        });
        wx.showToast({ title: "已加入收藏", icon: "none" });
      }
    } catch (err) {
      const message = extractErrorMessage(err, "收藏操作失败");
      this.setData({
        favoriteErrorMsg: isFavoriteDisabledError(message) ? "收藏功能未开启，请联系管理员。" : message,
      });
      wx.showToast({ title: "操作失败", icon: "none" });
    } finally {
      this.setData({ [loadingKey]: false }, () => this.syncFavoriteButtonTexts());
    }
  },

  togglePoemFavorite() {
    this.toggleFavorite(FAVORITE_TYPE_POEM);
  },

  toggleGuochaoFavorite() {
    this.toggleFavorite(FAVORITE_TYPE_GUOCHAO);
  },

  onUnload() {
    if (this._keyboardHandler && wx.offKeyboardHeightChange) {
      wx.offKeyboardHeightChange(this._keyboardHandler);
    }
    this.clearMediaGeneratePollTimer();
  },

  scrollToEmailSection() {
    this.setData({ emailSheetVisible: true });
  },

  handleEmailFocus() {
    this.setData({
      emailFocused: true,
      emailSheetVisible: true,
    });
  },

  handleEmailBlur() {
    const normalized = normalizeEmail(this.data.email);
    this.setData({
      emailFocused: false,
      emailError: getEmailError(normalized),
    });
  },

  onPoetImageError(event) {
    this.retryImageByField("poet", event);
  },

  onGuochaoImageError(event) {
    this.retryImageByField("guochao", event);
  },

  onPoetImageLoad() {
    this.setData({
      poetImageLoading: false,
      poetImageFailed: false,
      poetImageErrorRetries: 0,
    });
  },

  onGuochaoImageLoad() {
    this.setData({
      guochaoImageLoading: false,
      guochaoImageFailed: false,
      guochaoImageErrorRetries: 0,
    });
  },

  onUserImageError() {
    this.setData({ userImageFailed: true });
  },

  toggleUserImageVisible() {
    this.setData({ userImageVisible: !this.data.userImageVisible });
  },

  removeUserImageForEmail() {
    const context = this._analysisContext || {};
    const req = pickRequest(context);
    clearRequestUserImageRefs(req);

    this.setData({
      userImagePreviewUrl: "",
      userImageVisible: false,
      userImageFailed: false,
      userImageRemoved: true,
      emailStatus: "",
    });
    wx.showToast({
      title: "已移除自拍图",
      icon: "none",
    });
  },

  openEmailSheet() {
    this.setData({
      emailSheetVisible: true,
      emailStatus: "",
      emailStatusClass: "",
    });
  },

  closeEmailSheet() {
    this.setData({
      emailSheetVisible: false,
      emailFocused: false,
    });
  },

  handleEmailPanelTap() {
    // keep sheet open
  },

  goStyleStudio() {
    wx.navigateTo({ url: "/pages/style/index" });
  },

  async startMediaGenerate() {
    if (this.data.mediaGenerateLoading) return;
    const style = safeText(this.data.mediaGenerateStyle) || MEDIA_STYLE_CLASSICAL;

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
        mediaGenerateTaskId: "",
        mediaGenerateLoading: true,
        mediaGenerateStatus: "submitting",
        mediaGenerateStatusText: "正在切换静态风格图...",
        mediaGenerateRetryable: false,
        mediaGenerateError: "",
        mediaGenerateResultUrl: "",
        mediaGenerateResultStyle: "",
      });

      const task = await createMediaGenerateTask(payload);
      const taskId = safeText(task && task.task_id);
      if (!taskId) {
        throw new Error("未拿到风格图片任务编号");
      }
      this.applyMediaGenerateData({
        mediaGenerateTaskId: taskId,
        mediaGenerateLoading: true,
        mediaGenerateStatus: safeText(task && task.status) || "queued",
        mediaGenerateStatusText: buildMediaGenerateStatusText(task),
        mediaGenerateRetryable: false,
        mediaGenerateError: "",
      });
      this.scheduleMediaGeneratePoll(taskId, task && task.poll_after_ms, 0);
    } catch (err) {
      const message = buildMediaGenerateFailureText("", (err && err.message) || "", style);
      this.applyMediaGenerateFailure(
        {
          error_code: "",
          message,
          retryable: true,
          style,
        },
        message
      );
      wx.showToast({
        title: "切换未发起",
        icon: "none",
      });
    }
  },

  handleEmailInput(event) {
    const raw = (event && event.detail && event.detail.value) || "";
    const normalized = normalizeEmail(raw);
    this.setData({
      email: raw,
      emailError: getEmailError(normalized),
      emailStatus: "",
      emailStatusClass: "",
    });
  },

  async ensureUserImageRefs() {
    if (this.data.userImageRemoved) {
      return { fileId: "", tempUrl: "" };
    }

    const context = this._analysisContext || {};
    const req = pickRequest(context);

    const existingFileId = pickUserImageFileId(req);
    const existingUrl = pickUserImageUrl(req);
    if (existingFileId || existingUrl) {
      return {
        fileId: existingFileId,
        tempUrl: existingUrl,
      };
    }

    const tempPath = pickUserImageTempPath(req);
    if (!tempPath) return { fileId: "", tempUrl: "" };

    wx.showLoading({ title: "补传图片中..." });
    try {
      const uploaded = await uploadTempFile(tempPath, "images");
      const fileId = (uploaded && uploaded.fileID) || "";
      const tempUrl = (uploaded && uploaded.tempFileURL) || "";
      if (!context.request) {
        context.request = {};
      }
      context.request.imageFileId = fileId;
      context.request.image_file_id = fileId;
      context.request.imageTempUrl = tempUrl;
      context.request.image_url = tempUrl;
      return {
        fileId,
        tempUrl,
      };
    } finally {
      wx.hideLoading();
    }
  },

  async ensureUserAudioRefs() {
    const context = this._analysisContext || {};
    const req = pickRequest(context);

    const existingFileId = pickUserAudioFileId(req);
    const existingUrl = pickUserAudioUrl(req);
    if (existingFileId || existingUrl) {
      return {
        fileId: existingFileId,
        tempUrl: existingUrl,
      };
    }

    const tempPath = pickUserAudioTempPath(req);
    if (!tempPath) return { fileId: "", tempUrl: "" };

    wx.showLoading({ title: "补传录音中..." });
    try {
      const uploaded = await uploadTempFile(tempPath, "audio");
      const fileId = (uploaded && uploaded.fileID) || "";
      const tempUrl = (uploaded && uploaded.tempFileURL) || "";
      if (!context.request) {
        context.request = {};
      }
      context.request.audioFileId = fileId;
      context.request.audio_file_id = fileId;
      context.request.audioTempUrl = tempUrl;
      context.request.audio_url = tempUrl;
      context.request.uploadedAudioFileId = fileId;
      context.request.uploaded_audio_file_id = fileId;
      context.request.uploadedAudioTempUrl = tempUrl;
      context.request.uploaded_audio_url = tempUrl;
      return {
        fileId,
        tempUrl,
      };
    } finally {
      wx.hideLoading();
    }
  },

  async submitEmail() {
    const toEmail = normalizeEmail(this.data.email);
    const emailError = !toEmail ? "请输入邮箱地址" : getEmailError(toEmail);
    if (emailError) {
      this.setData({
        emailError,
        emailSheetVisible: true,
      });
      wx.showToast({ title: emailError, icon: "none" });
      return;
    }

    this.setData({
      email: toEmail,
      emailError: "",
    });

    const context = this._analysisContext || {};
    const req = pickRequest(context);
    const resp = pickResponse(context);
    const systemFields = pickSystemFields(resp);
    const reqText = safeText(req.text);
    const transcriptText = safeText(systemFields.speech_transcript);
    const thoughtsBlocks = [];
    if (reqText) thoughtsBlocks.push(`用户输入：${reqText}`);
    if (transcriptText) thoughtsBlocks.push(`语音转写：${transcriptText}`);
    const thoughtsText = thoughtsBlocks.join("\n\n");

    this.setData({
      isSendingEmail: true,
      emailStatus: "",
      emailStatusClass: "",
    });

    try {
      const userImageRefs = await this.ensureUserImageRefs();
      const userAudioRefs = await this.ensureUserAudioRefs();

      const payload = {
        to_email: toEmail,
        analysis_request_id: this.data.requestId || undefined,
        thoughts: thoughtsText || "",
        poem_text: [this.data.poet, this.data.poemText, this.data.interpretation]
          .filter(Boolean)
          .join("\n"),
        comfort_text: [this.data.guochaoName, this.data.comfort, `今日建议：${this.data.dailySuggestion}`]
          .filter(Boolean)
          .join("：\n"),
        user_image_url: userImageRefs.tempUrl || undefined,
        user_image_file_id: userImageRefs.fileId || undefined,
        user_audio_url: userAudioRefs.tempUrl || undefined,
        user_audio_file_id: userAudioRefs.fileId || undefined,
        poet_image_file_id: resp.poet_image_url || this.data.poetImageUrl || undefined,
        guochao_image_file_id: resp.guochao_image_url || this.data.guochaoImageUrl || undefined,
      };

      const result = await sendEmail(payload);
      this.setData({
        emailStatus: result && result.success === false ? "邮件发送失败" : "邮件发送成功！",
        emailStatusClass: result && result.success === false ? "error" : "success",
      });
      wx.showToast({
        title: result.success ? "发送成功" : "发送失败",
        icon: "none",
      });
    } catch (err) {
      this.setData({
        emailStatus: "邮件发送失败",
        emailStatusClass: "error",
      });
      wx.showToast({
        title: "发送失败",
        icon: "none",
      });
    } finally {
      this.setData({ isSendingEmail: false });
    }
  },

  backHome() {
    requestAnalyzeWorkspaceReset("result_reanalyze");
    wx.switchTab({
      url: ANALYZE_TAB,
      fail() {
        wx.reLaunch({ url: ANALYZE_TAB });
      },
    });
  },

  goHistory() {
    wx.navigateTo({ url: "/pages/history/index" });
  },

  goHomeTab() {
    wx.switchTab({
      url: HOME_TAB,
      fail() {
        wx.reLaunch({ url: HOME_TAB });
      },
    });
  },

  goJourneyTab() {
    wx.switchTab({
      url: JOURNEY_TAB,
      fail() {
        wx.reLaunch({ url: JOURNEY_TAB });
      },
    });
  },

  goCalendar() {
    wx.navigateTo({ url: "/pages/calendar/index" });
  },

  goReport() {
    wx.navigateTo({ url: "/pages/report/index" });
  },

  goFavorites() {
    wx.switchTab({ url: FAVORITES_TAB });
  },

  goShareCard() {
    const payload = buildSharePayloadFromData(this.data);
    try {
      wx.setStorageSync(SHARE_PAYLOAD_STORAGE_KEY, payload);
    } catch (err) {
      // ignore
    }
    wx.navigateTo({ url: "/pages/share/index" });
  },
});
