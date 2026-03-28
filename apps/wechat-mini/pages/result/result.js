const {
  deleteFavoriteItem,
  getFavoriteStatus,
  getRetentionCalendar,
  normalizeAssetUrl,
  sendEmail,
  upsertFavorite,
} = require("../../services/api");
const { uploadTempFile } = require("../../services/cloud");

const DEFAULT_DAILY_SUGGESTION = "今天先做一件你能马上完成的小行动，逐步稳住状态。";
const FAVORITE_TYPE_POEM = "poem";
const FAVORITE_TYPE_GUOCHAO = "guochao";
const SHARE_PAYLOAD_STORAGE_KEY = "ec_share_payload";
const RESULT_IMAGE_RETRY_LIMIT = 2;

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
  const provider = safeText(systemFields && systemFields.speech_transcript_provider);
  const error = safeText(systemFields && systemFields.speech_transcript_error);
  if (!status) return "";

  if (status === "provider_unconfigured") {
    return "语音转写未配置（SPEECH_STT_ENDPOINT 为空），当前仅使用录音音色特征参与分析。";
  }
  if (status === "service_disabled") {
    return "语音转写已由管理员关闭，当前仅使用录音音色特征参与分析。";
  }
  if (status === "request_failed" || status === "runtime_error") {
    return "语音转写失败，当前已降级为仅使用录音音色特征参与分析。";
  }
  if (status.indexOf("rejected:") === 0) {
    return `语音质量未通过：${error || status}`;
  }
  if (status === "empty") {
    return "语音转写结果为空，建议在更安静环境重试。";
  }
  if (status === "ok" && provider) {
    return `语音转写已完成（${provider}）。`;
  }
  if (provider) {
    return `语音转写状态：${status}（${provider}）。`;
  }
  return `语音转写状态：${status}`;
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
    email: "",
    emailError: "",
    emailFocused: false,
    keyboardHeight: 0,
    bottomPaddingPx: 0,
    isSendingEmail: false,
    emailStatus: "",
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
    });
    this.refreshRetentionSnapshot();
    this.refreshFavoriteStatus();

    if (wx.onKeyboardHeightChange) {
      this._keyboardHandler = (res) => {
        const height = Math.max(0, (res && res.height) || 0);
        this.setData(
          {
            keyboardHeight: height,
            bottomPaddingPx: height > 0 ? height + 24 : 0,
          },
          () => {
            if (height > 0) this.scrollToEmailSection();
          }
        );
      };
      wx.onKeyboardHeightChange(this._keyboardHandler);
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
        retentionErrorMsg: (err && err.message) || "打卡状态刷新失败",
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
  },

  scrollToEmailSection() {
    wx.pageScrollTo({
      selector: "#email-section",
      duration: 120,
      offsetTop: 60,
      fail() {
        // ignore
      },
    });
  },

  handleEmailFocus() {
    this.setData({ emailFocused: true });
    this.scrollToEmailSection();
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

  handleEmailInput(event) {
    const raw = (event && event.detail && event.detail.value) || "";
    const normalized = normalizeEmail(raw);
    this.setData({
      email: raw,
      emailError: getEmailError(normalized),
      emailStatus: "",
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
      this.setData({ emailError });
      this.scrollToEmailSection();
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
        emailStatus: result.message || "邮件发送完成",
      });
      wx.showToast({
        title: result.success ? "发送成功" : "发送失败",
        icon: "none",
      });
    } catch (err) {
      this.setData({
        emailStatus: err.message || "邮件发送失败",
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
    wx.navigateBack({
      delta: 1,
      fail() {
        wx.reLaunch({ url: "/pages/index/index" });
      },
    });
  },

  goHistory() {
    wx.navigateTo({ url: "/pages/history/index" });
  },

  goCalendar() {
    wx.navigateTo({ url: "/pages/calendar/index" });
  },

  goReport() {
    wx.navigateTo({ url: "/pages/report/index" });
  },

  goFavorites() {
    wx.navigateTo({ url: "/pages/favorites/index" });
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
