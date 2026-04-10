Page({
  data: {
    photoTempPath: "",
    isCapturing: false,
    isCameraVisible: false,
    isCameraReady: false,
    cameraResolution: "high",
    stageHeightPx: 520,
    errorMsg: "",
  },

  onLoad() {
    if (typeof this.getOpenerEventChannel === "function") {
      this.openerEventChannel = this.getOpenerEventChannel();
    }
    try {
      const systemInfo = wx.getSystemInfoSync();
      const model = `${systemInfo.model || ""}`.toLowerCase();
      const system = `${systemInfo.system || ""}`.toLowerCase();
      const isIOS = system.includes("ios") || model.includes("iphone");
      const windowHeight = Number(systemInfo.windowHeight || 0);
      const windowWidth = Number(systemInfo.windowWidth || 0);
      const maxStageHeight = Math.max(360, windowHeight - 270);
      const portraitStageHeight = Math.round((windowWidth - 48) * 1.28);
      const stageHeightPx = Math.max(360, Math.min(maxStageHeight, portraitStageHeight));
      this.setData({
        cameraResolution: isIOS ? "medium" : "high",
        stageHeightPx,
      });
    } catch (err) {
      // ignore
    }
  },

  onReady() {
    this.cameraContext = wx.createCameraContext();
    setTimeout(() => {
      this.setData({
        isCameraVisible: true,
      });
    }, 180);
  },

  handleCameraError(event) {
    const detail = (event && event.detail) || {};
    const message = (detail && (detail.errMsg || detail.message)) || "摄像头初始化失败";
    this.setData({
      errorMsg: message,
      isCameraReady: false,
    });
    wx.showToast({
      title: "摄像头不可用",
      icon: "none",
    });
  },

  handleCameraInitDone() {
    this.setData({
      isCameraReady: true,
      errorMsg: "",
    });
  },

  handleCameraStop() {
    this.setData({
      isCameraReady: false,
    });
  },

  takePhoto() {
    if (this.data.isCapturing) return;
    if (!this.data.isCameraReady) {
      wx.showToast({
        title: "摄像头准备中",
        icon: "none",
      });
      return;
    }
    if (!this.cameraContext || typeof this.cameraContext.takePhoto !== "function") {
      wx.showToast({
        title: "摄像头尚未准备好",
        icon: "none",
      });
      return;
    }

    this.setData({
      isCapturing: true,
      errorMsg: "",
    });

    this.cameraContext.takePhoto({
      quality: "high",
      success: (res) => {
        const tempPath = (res && res.tempImagePath) || "";
        if (!tempPath) {
          this.setData({ errorMsg: "未获取到自拍照片" });
          wx.showToast({
            title: "拍照失败",
            icon: "none",
          });
          return;
        }
        this.setData({
          photoTempPath: tempPath,
          errorMsg: "",
        });
      },
      fail: (err) => {
        const message = (err && (err.errMsg || err.message)) || "拍照失败";
        this.setData({ errorMsg: message });
        wx.showToast({
          title: "拍照失败",
          icon: "none",
        });
      },
      complete: () => {
        this.setData({ isCapturing: false });
      },
    });
  },

  retakePhoto() {
    this.setData({
      photoTempPath: "",
      isCameraReady: false,
      errorMsg: "",
    });
    setTimeout(() => {
      this.setData({
        isCameraVisible: false,
      });
      setTimeout(() => {
        this.cameraContext = wx.createCameraContext();
        this.setData({
          isCameraVisible: true,
        });
      }, 80);
    }, 0);
  },

  confirmPhoto() {
    const tempPath = (this.data.photoTempPath || "").trim();
    if (!tempPath) return;
    if (this.openerEventChannel && typeof this.openerEventChannel.emit === "function") {
      this.openerEventChannel.emit("selfieCaptured", {
        tempFilePath: tempPath,
      });
    }
    wx.navigateBack({
      delta: 1,
    });
  },

  closePage() {
    wx.navigateBack({
      delta: 1,
      fail() {
        wx.switchTab({ url: "/pages/analyze/index" });
      },
    });
  },
});
