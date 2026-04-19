const {
  getDashboardOverview,
  getCheckinStatus,
  getRetentionCalendar,
  getRetentionWeeklyReport,
  getTodayHistory,
  listFavorites,
  listHistory,
} = require("./api");

const DASHBOARD_CACHE_TTL_MS = 20 * 1000;
const HISTORY_LIMIT = 5;
const FAVORITES_LIMIT = 2;

let cachedSnapshot = null;
let inFlightPromise = null;

function toMonthText(dateObj) {
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  return `${yyyy}-${mm}`;
}

function toDateText(dateObj) {
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  const dd = String(dateObj.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function buildCacheKey(now = new Date()) {
  return `${toMonthText(now)}|${toDateText(now)}`;
}

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function isCacheFresh(snapshot, nowTs = Date.now()) {
  if (!snapshot || typeof snapshot !== "object") return false;
  const fetchedAt = Number(snapshot.fetchedAt) || 0;
  if (!fetchedAt) return false;
  if (nowTs - fetchedAt > DASHBOARD_CACHE_TTL_MS) return false;
  return snapshot.cacheKey === buildCacheKey(new Date(nowTs));
}

function toSettledSection(section) {
  const status = safeText(section && section.status).toLowerCase();
  if (status === "fulfilled") {
    const value = section && typeof section.value === "object" ? section.value : {};
    return {
      status: "fulfilled",
      value,
    };
  }
  const reason = safeText(section && section.reason) || "dashboard section unavailable";
  return {
    status: "rejected",
    reason,
  };
}

function normalizeAggregateSnapshot(raw, now = new Date()) {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  return {
    fetchedAt: Date.now(),
    cacheKey: buildCacheKey(now),
    calendarRes: toSettledSection(raw.calendar),
    reportRes: toSettledSection(raw.weekly_report),
    historyRes: toSettledSection(raw.history),
    favoritesRes: toSettledSection(raw.favorites),
    todayHistoryRes: toSettledSection(raw.today_history),
    checkinRes: toSettledSection(raw.checkin),
  };
}

async function fetchDashboardOverviewLegacy(now = new Date()) {
  const monthText = toMonthText(now);
  const dateText = toDateText(now);
  const [calendarRes, reportRes, historyRes, favoritesRes, todayHistoryRes, checkinRes] = await Promise.allSettled([
    getRetentionCalendar(monthText),
    getRetentionWeeklyReport(),
    listHistory({ limit: HISTORY_LIMIT, offset: 0 }),
    listFavorites({ limit: FAVORITES_LIMIT, offset: 0 }),
    getTodayHistory(dateText),
    getCheckinStatus(),
  ]);

  return {
    fetchedAt: Date.now(),
    cacheKey: buildCacheKey(now),
    calendarRes,
    reportRes,
    historyRes,
    favoritesRes,
    todayHistoryRes,
    checkinRes,
  };
}

async function fetchDashboardOverview() {
  const now = new Date();
  const monthText = toMonthText(now);
  const dateText = toDateText(now);
  try {
    const aggregate = await getDashboardOverview({
      month: monthText,
      date: dateText,
      historyLimit: HISTORY_LIMIT,
      favoritesLimit: FAVORITES_LIMIT,
    });
    const snapshot = normalizeAggregateSnapshot(aggregate, now);
    if (snapshot) {
      return snapshot;
    }
  } catch (err) {
    // fallback to legacy multi-request strategy when aggregate endpoint is unavailable
  }
  return fetchDashboardOverviewLegacy(now);
}

async function getDashboardOverviewSnapshot(options = {}) {
  const forceRefresh = !!(options && options.forceRefresh);
  const nowTs = Date.now();
  if (!forceRefresh && isCacheFresh(cachedSnapshot, nowTs)) {
    return {
      ...cachedSnapshot,
      fromCache: true,
    };
  }

  if (inFlightPromise) {
    const snapshot = await inFlightPromise;
    return {
      ...snapshot,
      fromCache: isCacheFresh(snapshot, Date.now()),
    };
  }

  inFlightPromise = fetchDashboardOverview()
    .then((snapshot) => {
      cachedSnapshot = snapshot;
      return snapshot;
    })
    .finally(() => {
      inFlightPromise = null;
    });

  const snapshot = await inFlightPromise;
  return {
    ...snapshot,
    fromCache: false,
  };
}

function invalidateDashboardOverviewCache() {
  cachedSnapshot = null;
}

module.exports = {
  getDashboardOverviewSnapshot,
  invalidateDashboardOverviewCache,
};
