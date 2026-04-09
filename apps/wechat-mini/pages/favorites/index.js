const { clearFavorites, deleteFavoriteItem, listFavorites } = require("../../services/api");
const { ensurePhase5Auth } = require("../../utils/auth-gate");
const { FAVORITES_TAB, setTabBarSelected } = require("../../utils/tabbar");

const PAGE_SIZE = 20;
const TYPE_ALL = "all";
const TAB_ITEMS = [
  { value: TYPE_ALL, label: "全部" },
  { value: "poem", label: "诗词" },
  { value: "guochao", label: "国潮" },
];
const TYPE_LABEL_MAP = {
  [TYPE_ALL]: "全部",
  poem: "诗词",
  guochao: "国潮",
};

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function buildTabs(activeType) {
  return TAB_ITEMS.map((item) => ({
    ...item,
    className: item.value === activeType ? "favorites-tab favorites-tab-active" : "favorites-tab",
  }));
}

function getTypeLabel(type) {
  return TYPE_LABEL_MAP[type] || TYPE_LABEL_MAP[TYPE_ALL];
}

function formatUpdatedAt(value) {
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

function normalizeTypeLabel(type) {
  if (type === "poem") {
    return { label: "诗词", className: "type-badge type-poem" };
  }
  if (type === "guochao") {
    return { label: "国潮", className: "type-badge type-guochao" };
  }
  return { label: "未分类", className: "type-badge" };
}

function buildFavoriteItemView(item) {
  const type = safeText(item && item.favorite_type);
  const typeMeta = normalizeTypeLabel(type);
  return {
    favoriteId: safeText(item && item.favorite_id),
    favoriteType: type,
    typeLabel: typeMeta.label,
    typeClassName: typeMeta.className,
    title: safeText(item && item.title) || "未命名收藏",
    subtitle: safeText(item && item.subtitle),
    contentSummary: safeText(item && item.content_summary),
    createdAtText: formatUpdatedAt(item && item.created_at),
    updatedAtText: formatUpdatedAt(item && item.updated_at),
  };
}

function buildEmptyText(activeType) {
  if (activeType === "poem") {
    return "还没有收藏诗词。";
  }
  if (activeType === "guochao") {
    return "还没有收藏国潮内容。";
  }
  return "还没有收藏内容。";
}

function extractErrorMessage(err, fallback) {
  return ((err && err.message) || fallback || "").trim();
}

function isFavoritesDisabledError(message) {
  return typeof message === "string" && message.includes("RETENTION_FAVORITES_DISABLED");
}

Page({
  data: {
    tabs: buildTabs(TYPE_ALL),
    activeType: TYPE_ALL,
    activeTypeLabel: getTypeLabel(TYPE_ALL),
    items: [],
    total: 0,
    nextOffset: 0,
    hasMore: false,
    isLoading: false,
    isLoadingMore: false,
    isClearing: false,
    errorMsg: "",
    emptyText: buildEmptyText(TYPE_ALL),
  },

  onShow() {
    if (ensurePhase5Auth(FAVORITES_TAB)) return;
    setTabBarSelected(this, FAVORITES_TAB);
    this.loadFavorites({ reset: true });
  },

  onPullDownRefresh() {
    this.loadFavorites({ reset: true }).finally(() => {
      wx.stopPullDownRefresh();
    });
  },

  onReachBottom() {
    if (this.data.hasMore) {
      this.loadMore();
    }
  },

  resolveFavoriteType() {
    return this.data.activeType === TYPE_ALL ? "" : this.data.activeType;
  },

  async loadFavorites(options = {}) {
    const reset = !!options.reset;
    if (reset) {
      if (this.data.isLoading) return;
    } else if (this.data.isLoadingMore || this.data.isLoading) {
      return;
    }

    const offset = reset ? 0 : this.data.nextOffset;
    this.setData({
      errorMsg: "",
      activeTypeLabel: getTypeLabel(this.data.activeType),
      isLoading: reset,
      isLoadingMore: !reset,
      emptyText: buildEmptyText(this.data.activeType),
    });

    try {
      const favoriteType = this.resolveFavoriteType();
      const response = await listFavorites({
        favoriteType,
        limit: PAGE_SIZE,
        offset,
      });
      const fetched = Array.isArray(response && response.items)
        ? response.items.map(buildFavoriteItemView)
        : [];

      const merged = reset ? fetched : this.data.items.concat(fetched);
      const total = Number(response && response.total) || merged.length;
      const nextOffset = offset + fetched.length;
      const hasMore = nextOffset < total;

      this.setData({
        items: merged,
        total,
        nextOffset,
        hasMore,
      });
    } catch (err) {
      const rawMessage = extractErrorMessage(err, "加载收藏失败，请稍后重试。");
      const message = isFavoritesDisabledError(rawMessage)
        ? "收藏功能未开启，请联系管理员。"
        : rawMessage;
      this.setData({ errorMsg: message });
    } finally {
      this.setData({
        isLoading: false,
        isLoadingMore: false,
      });
    }
  },

  handleTabChange(event) {
    const nextType = safeText(event && event.currentTarget && event.currentTarget.dataset.type) || TYPE_ALL;
    if (nextType === this.data.activeType) return;

    this.setData({
      activeType: nextType,
      activeTypeLabel: getTypeLabel(nextType),
      tabs: buildTabs(nextType),
      items: [],
      total: 0,
      nextOffset: 0,
      hasMore: false,
      emptyText: buildEmptyText(nextType),
      errorMsg: "",
    });
    this.loadFavorites({ reset: true });
  },

  async handleDeleteFavorite(event) {
    const favoriteId = safeText(event && event.currentTarget && event.currentTarget.dataset.id);
    if (!favoriteId) return;

    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: "取消收藏",
        content: "确认取消这条收藏吗？",
        confirmText: "取消收藏",
        cancelText: "保留",
        success(res) {
          resolve(!!(res && res.confirm));
        },
        fail() {
          resolve(false);
        },
      });
    });
    if (!confirmed) return;

    try {
      await deleteFavoriteItem(favoriteId);
      const remaining = this.data.items.filter((item) => item.favoriteId !== favoriteId);
      const nextTotal = Math.max(0, Number(this.data.total) - 1);
      this.setData({
        items: remaining,
        total: nextTotal,
        hasMore: this.data.nextOffset < nextTotal,
      });
      wx.showToast({
        title: "已取消收藏",
        icon: "none",
      });
    } catch (err) {
      const message = extractErrorMessage(err, "取消收藏失败，请稍后重试。");
      this.setData({ errorMsg: message });
      wx.showToast({
        title: "操作失败",
        icon: "none",
      });
    }
  },

  async handleClearCurrentType() {
    const favoriteType = this.resolveFavoriteType();
    const targetText = favoriteType ? "当前类型" : "全部";

    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: `清空${targetText}收藏`,
        content: "该操作不可撤销，是否继续？",
        confirmText: "确认清空",
        cancelText: "取消",
        success(res) {
          resolve(!!(res && res.confirm));
        },
        fail() {
          resolve(false);
        },
      });
    });
    if (!confirmed) return;

    this.setData({ isClearing: true, errorMsg: "" });
    try {
      await clearFavorites(favoriteType || "");
      wx.showToast({ title: "已清空收藏", icon: "none" });
      await this.loadFavorites({ reset: true });
    } catch (err) {
      const message = extractErrorMessage(err, "清空收藏失败，请稍后重试。");
      this.setData({ errorMsg: message });
      wx.showToast({ title: "清空失败", icon: "none" });
    } finally {
      this.setData({ isClearing: false });
    }
  },

  loadMore() {
    if (!this.data.hasMore) return;
    this.loadFavorites({ reset: false });
  },

  retryLoad() {
    if (this.data.isLoading || this.data.isLoadingMore) return;
    this.loadFavorites({ reset: true });
  },
});
