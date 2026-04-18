const QUIZ_PAPER_CACHE_STORAGE_KEY = "ec_study_quiz_paper_cache_v1";
const QUIZ_PAPER_CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
const QUIZ_PAPER_PREFETCH_INTERVAL_MS = 20 * 60 * 1000;

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function isValidQuizPaperPayload(payload) {
  if (!payload || typeof payload !== "object") return false;
  if (!safeText(payload.paper_id)) return false;
  const questions = payload.questions;
  return Array.isArray(questions) && questions.length > 0;
}

function getQuizPaperCacheMeta() {
  try {
    const payload = wx.getStorageSync(QUIZ_PAPER_CACHE_STORAGE_KEY);
    if (!payload || typeof payload !== "object") return null;
    const savedAt = Number(payload.savedAt) || 0;
    const paper = payload.paper;
    if (!savedAt || !isValidQuizPaperPayload(paper)) return null;
    const ageMs = Math.max(0, Date.now() - savedAt);
    return {
      savedAt,
      ageMs,
      expired: ageMs > QUIZ_PAPER_CACHE_MAX_AGE_MS,
      paper,
    };
  } catch (err) {
    return null;
  }
}

function readQuizPaperCache(options = {}) {
  const allowExpired = !!options.allowExpired;
  const meta = getQuizPaperCacheMeta();
  if (!meta) return null;
  if (!allowExpired && meta.expired) return null;
  return meta.paper;
}

function writeQuizPaperCache(paper) {
  if (!isValidQuizPaperPayload(paper)) return;
  try {
    wx.setStorageSync(QUIZ_PAPER_CACHE_STORAGE_KEY, {
      savedAt: Date.now(),
      paper,
    });
  } catch (err) {
    // ignore
  }
}

function shouldPrefetchQuizPaper(minIntervalMs = QUIZ_PAPER_PREFETCH_INTERVAL_MS) {
  const interval = Math.max(30 * 1000, Number(minIntervalMs) || QUIZ_PAPER_PREFETCH_INTERVAL_MS);
  const meta = getQuizPaperCacheMeta();
  if (!meta) return true;
  if (meta.expired) return true;
  return meta.ageMs >= interval;
}

module.exports = {
  QUIZ_PAPER_CACHE_STORAGE_KEY,
  QUIZ_PAPER_CACHE_MAX_AGE_MS,
  QUIZ_PAPER_PREFETCH_INTERVAL_MS,
  isValidQuizPaperPayload,
  getQuizPaperCacheMeta,
  readQuizPaperCache,
  writeQuizPaperCache,
  shouldPrefetchQuizPaper,
};
