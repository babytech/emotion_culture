const { normalizeAssetUrl, sendEmail } = require("../../services/api");

function normalizeEmail(email) {
  return (email || "").trim();
}

function isEmailValid(email) {
  if (!email.includes("@")) return false;
  const domain = email.split("@")[1] || "";
  return domain.includes(".");
}

Page({
  data: {
    hasData: false,
    emotionCode: "",
    emotionLabel: "",
    poet: "",
    poemText: "",
    interpretation: "",
    guochaoName: "",
    comfort: "",
    poetImageUrl: "",
    guochaoImageUrl: "",
    poetImageFailed: false,
    guochaoImageFailed: false,
    email: "",
    isSendingEmail: false,
    emailStatus: "",
  },

  onLoad() {
    const app = getApp();
    const context = app.globalData.latestAnalyzeContext;
    const response = context && context.response;

    if (!response) {
      this.setData({ hasData: false });
      return;
    }

    this._analysisContext = context;

    this.setData({
      hasData: true,
      emotionCode: response.emotion.code || "",
      emotionLabel: response.emotion.label || "",
      poet: response.poem.poet || "",
      poemText: response.poem.text || "",
      interpretation: response.poem.interpretation || "",
      guochaoName: response.guochao.name || "",
      comfort: response.guochao.comfort || "",
      poetImageUrl: normalizeAssetUrl(response.poet_image_url || ""),
      guochaoImageUrl: normalizeAssetUrl(response.guochao_image_url || ""),
      poetImageFailed: false,
      guochaoImageFailed: false,
    });
  },

  onPoetImageError() {
    this.setData({ poetImageFailed: true });
  },

  onGuochaoImageError() {
    this.setData({ guochaoImageFailed: true });
  },

  handleEmailInput(event) {
    this.setData({
      email: event.detail.value,
      emailStatus: "",
    });
  },

  async submitEmail() {
    const toEmail = normalizeEmail(this.data.email);
    if (!toEmail) {
      wx.showToast({ title: "请输入邮箱地址", icon: "none" });
      return;
    }
    if (!isEmailValid(toEmail)) {
      wx.showToast({ title: "邮箱格式不正确", icon: "none" });
      return;
    }

    const context = this._analysisContext || {};
    const req = context.request || {};

    this.setData({
      isSendingEmail: true,
      emailStatus: "",
    });

    try {
      const payload = {
        to_email: toEmail,
        thoughts: req.text || "",
        poem_text: [this.data.poet, this.data.poemText, this.data.interpretation]
          .filter(Boolean)
          .join("\n"),
        comfort_text: [this.data.guochaoName, this.data.comfort]
          .filter(Boolean)
          .join("：\n"),
        user_image_file_id: req.imageFileId || undefined,
        poet_image_file_id: this.data.poetImageUrl || undefined,
        guochao_image_file_id: this.data.guochaoImageUrl || undefined,
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
});
