const { analyze } = require("../../services/api");
const { uploadTempFile } = require("../../services/cloud");

const recorder = wx.getRecorderManager();

Page({
  data: {
    text: "",
    imageTempPath: "",
    audioTempPath: "",
    isRecording: false,
    recordSeconds: 0,
    isSubmitting: false,
    errorMsg: "",
  },

  onLoad() {
    this.bindRecorderEvents();
  },

  onUnload() {
    this.stopRecordTimer();
    if (this.data.isRecording) {
      try {
        recorder.stop();
      } catch (e) {
        // ignore
      }
    }
  },

  bindRecorderEvents() {
    if (this._recorderBound) return;
    this._recorderBound = true;

    recorder.onStart(() => {
      this.setData({
        isRecording: true,
        recordSeconds: 0,
      });
      this.startRecordTimer();
    });

    recorder.onStop((res) => {
      this.stopRecordTimer();
      this.setData({
        isRecording: false,
        audioTempPath: res.tempFilePath || "",
      });
    });

    recorder.onError((err) => {
      this.stopRecordTimer();
      this.setData({ isRecording: false });
      wx.showToast({
        title: err.errMsg || "录音失败",
        icon: "none",
      });
    });
  },

  startRecordTimer() {
    this.stopRecordTimer();
    this._recordTimer = setInterval(() => {
      this.setData({
        recordSeconds: this.data.recordSeconds + 1,
      });
    }, 1000);
  },

  stopRecordTimer() {
    if (this._recordTimer) {
      clearInterval(this._recordTimer);
      this._recordTimer = null;
    }
  },

  handleTextInput(event) {
    this.setData({
      text: event.detail.value,
      errorMsg: "",
    });
  },

  async chooseImage() {
    try {
      const res = await wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sourceType: ["camera", "album"],
      });

      const file = res.tempFiles && res.tempFiles[0];
      if (!file || !file.tempFilePath) {
        throw new Error("未获取到图片");
      }

      this.setData({
        imageTempPath: file.tempFilePath,
        errorMsg: "",
      });
    } catch (err) {
      if ((err.errMsg || "").includes("cancel")) return;
      wx.showToast({
        title: err.message || "选择图片失败",
        icon: "none",
      });
    }
  },

  clearImage() {
    this.setData({ imageTempPath: "" });
  },

  startRecord() {
    if (this.data.isRecording) return;

    recorder.start({
      duration: 60000,
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 96000,
      format: "mp3",
      frameSize: 50,
    });
  },

  stopRecord() {
    if (!this.data.isRecording) return;
    recorder.stop();
  },

  clearAudio() {
    this.setData({
      audioTempPath: "",
      recordSeconds: 0,
    });
  },

  async submitAnalyze() {
    const text = (this.data.text || "").trim();
    const imageTempPath = this.data.imageTempPath;
    const audioTempPath = this.data.audioTempPath;

    if (!text && !imageTempPath && !audioTempPath) {
      this.setData({ errorMsg: "请至少提供文本、图片或语音中的一种输入。" });
      return;
    }

    this.setData({
      isSubmitting: true,
      errorMsg: "",
    });

    try {
      let imageFileId = "";
      let audioFileId = "";

      if (imageTempPath) {
        wx.showLoading({ title: "上传图片中..." });
        imageFileId = await uploadTempFile(imageTempPath, "images");
      }

      if (audioTempPath) {
        wx.showLoading({ title: "上传语音中..." });
        audioFileId = await uploadTempFile(audioTempPath, "audio");
      }

      wx.showLoading({ title: "分析中..." });
      const result = await analyze({
        text: text || undefined,
        image_file_id: imageFileId || undefined,
        audio_file_id: audioFileId || undefined,
        client: {
          platform: "mp-weixin",
          version: "0.1.0",
        },
      });

      const app = getApp();
      app.globalData.latestAnalyzeContext = {
        request: {
          text,
          imageFileId,
          audioFileId,
        },
        response: result,
      };

      wx.navigateTo({
        url: "/pages/result/result",
      });
    } catch (err) {
      this.setData({
        errorMsg: err.message || "分析失败，请稍后重试。",
      });
      wx.showToast({
        title: "分析失败",
        icon: "none",
      });
    } finally {
      wx.hideLoading();
      this.setData({ isSubmitting: false });
    }
  },
});
