const { analyze, createAnalyzeTask, getAnalyzeTask } = require("../../services/api");
const { uploadTempFile } = require("../../services/cloud");

const recorder = wx.getRecorderManager();
const IMAGE_COMPRESS_SKIP_BYTES = 900 * 1024;
const IMAGE_COMPRESS_MEDIUM_BYTES = 2 * 1024 * 1024;
const IMAGE_COMPRESS_HEAVY_BYTES = 4 * 1024 * 1024;
const AUDIO_ALLOWED_EXTENSIONS = [".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".webm"];
const AUDIO_MIN_SECONDS = 1;
const AUDIO_MIN_FILE_SIZE_BYTES = 6000;
const SUBMIT_STAGE = {
  IDLE: "idle",
  UPLOADING: "uploading",
  ANALYZING: "analyzing",
  RENDERING: "rendering",
  FAILED: "failed",
};
const ANALYZE_POLL_DEFAULT_INTERVAL_MS = 1200;
const ANALYZE_POLL_TIMEOUT_MS = 240000;
const ANALYZE_POLL_TRANSIENT_RETRY_LIMIT = 12;

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function normalizeTaskStatus(value) {
  return ((value || "").trim() || "queued").toLowerCase();
}

function buildTaskStageText(task) {
  const status = normalizeTaskStatus(task && task.status);
  const statusMessage = ((task && task.status_message) || "").trim();
  if (status === "queued") {
    return statusMessage || "分析排队中：正在等待服务处理...";
  }
  if (status === "running") {
    return statusMessage || "分析中：正在生成情绪结果...";
  }
  if (status === "succeeded") {
    return "结果生成中：正在打开结果页...";
  }
  if (status === "failed") {
    return statusMessage || "分析失败";
  }
  return "分析中：正在处理...";
}

function getFileExtension(path) {
  const value = (path || "").trim();
  const index = value.lastIndexOf(".");
  if (index < 0) return "";
  return value.slice(index).toLowerCase();
}

function getFileSize(path) {
  return new Promise((resolve) => {
    try {
      wx.getFileSystemManager().stat({
        path,
        success(res) {
          resolve((res.stats && res.stats.size) || 0);
        },
        fail() {
          resolve(0);
        },
      });
    } catch (err) {
      resolve(0);
    }
  });
}

function compressImage(path, quality) {
  return new Promise((resolve, reject) => {
    wx.compressImage({
      src: path,
      quality,
      success(res) {
        resolve((res && res.tempFilePath) || path);
      },
      fail(err) {
        reject(err);
      },
    });
  });
}

function extractTempImagePath(res) {
  return (
    (res &&
      res.tempFiles &&
      res.tempFiles[0] &&
      (res.tempFiles[0].tempFilePath || res.tempFiles[0].path)) ||
    (res && res.tempFilePaths && res.tempFilePaths[0]) ||
    ""
  );
}

async function prepareImageForUpload(path) {
  const sizeBefore = await getFileSize(path);
  if (sizeBefore > 0 && sizeBefore <= IMAGE_COMPRESS_SKIP_BYTES) {
    return { path, compressed: false, sizeBefore, sizeAfter: sizeBefore };
  }

  let quality = 82;
  if (sizeBefore >= IMAGE_COMPRESS_HEAVY_BYTES) quality = 68;
  else if (sizeBefore >= IMAGE_COMPRESS_MEDIUM_BYTES) quality = 76;

  try {
    const compressedPath = await compressImage(path, quality);
    const sizeAfter = await getFileSize(compressedPath);
    if (!sizeAfter || (sizeBefore > 0 && sizeAfter >= sizeBefore)) {
      return { path, compressed: false, sizeBefore, sizeAfter: sizeBefore };
    }
    return { path: compressedPath, compressed: compressedPath !== path, sizeBefore, sizeAfter };
  } catch (err) {
    console.warn("compressImage failed, fallback to original", err);
    return { path, compressed: false, sizeBefore, sizeAfter: sizeBefore };
  }
}

function buildRecoverableAnalyzeError(err) {
  const message = ((err && err.message) || "分析失败，请稍后重试。").trim();
  if (!message) {
    return "分析失败，请重试。你之前填写的内容已保留。";
  }

  if (message.includes("分析任务仍在处理中")) {
    return "分析任务仍在云端处理中，可稍后再次点击“提交分析”继续查询，无需重新上传自拍或录音。";
  }

  const lowerMsg = message.toLowerCase();
  if (message.includes("102002") || message.includes("请求超时") || lowerMsg.includes("timeout")) {
    return "云端请求超时，请检查网络后重试。若连续超时，可先仅用文字输入提交。";
  }
  if (message.includes("[VOICE_")) {
    return `${message} 可重新录音，或改用文字输入后再次提交。`;
  }
  if (message.includes("[FACE_")) {
    return `${message} 可重新自拍后再次提交。`;
  }
  return `${message} 可直接重试，原输入已保留。`;
}

async function validateAudioBeforeUpload(audioTempPath, recordSeconds) {
  const path = (audioTempPath || "").trim();
  if (!path) {
    return { ok: true, message: "" };
  }

  const extension = getFileExtension(path);
  if (extension && !AUDIO_ALLOWED_EXTENSIONS.includes(extension)) {
    return {
      ok: false,
      message: "录音格式不支持，请重新录制。",
    };
  }

  const safeSeconds = Number(recordSeconds) || 0;
  if (safeSeconds > 0 && safeSeconds < AUDIO_MIN_SECONDS) {
    return {
      ok: false,
      message: "录音时长过短，请重新录音后提交。",
    };
  }

  const sizeBytes = await getFileSize(path);
  if (!sizeBytes) {
    return {
      ok: false,
      message: "录音文件无法读取，请重新录音。",
    };
  }
  if (sizeBytes < AUDIO_MIN_FILE_SIZE_BYTES) {
    return {
      ok: false,
      message: "录音音量过小或时长过短，请重新录音。",
    };
  }

  return { ok: true, message: "" };
}

Page({
  data: {
    text: "",
    imageTempPath: "",
    pendingSelfiePath: "",
    audioTempPath: "",
    isRecording: false,
    recordSeconds: 0,
    isSubmitting: false,
    submitStage: SUBMIT_STAGE.IDLE,
    submitStatusText: "",
    submitButtonText: "提交分析",
    errorMsg: "",
    isDevtools: false,
  },

  onLoad() {
    let isDevtools = false;
    try {
      const sysInfo = wx.getSystemInfoSync();
      isDevtools = !!sysInfo && sysInfo.platform === "devtools";
    } catch (err) {
      isDevtools = false;
    }
    this.setData({ isDevtools });
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
        submitStage: SUBMIT_STAGE.IDLE,
        submitStatusText: "",
        submitButtonText: "提交分析",
        errorMsg: "",
      });
      this.startRecordTimer();
    });

    recorder.onStop((res) => {
      this.stopRecordTimer();
      this.setData({
        isRecording: false,
        audioTempPath: res.tempFilePath || "",
        submitStage: SUBMIT_STAGE.IDLE,
        submitStatusText: "",
        submitButtonText: "提交分析",
        errorMsg: "",
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
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
  },

  async chooseSelfie() {
    let tempPath = "";
    try {
      const mediaRes = await wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sizeType: ["original"],
        sourceType: ["camera"],
        camera: "front",
      });
      tempPath = extractTempImagePath(mediaRes);
    } catch (err) {
      const message = (err && err.errMsg) || "";
      if (!message.includes("cancel")) {
        try {
          const imageRes = await wx.chooseImage({
            count: 1,
            sizeType: ["original"],
            sourceType: ["camera"],
          });
          tempPath = extractTempImagePath(imageRes);
        } catch (fallbackErr) {
          if ((fallbackErr.errMsg || "").includes("cancel")) return;
          wx.showToast({
            title: fallbackErr.message || "拍照失败",
            icon: "none",
          });
          return;
        }
      } else {
        return;
      }
    }

    if (!tempPath) {
      wx.showToast({
        title: "未获取到自拍照片",
        icon: "none",
      });
      return;
    }

    this.setData({
      imageTempPath: "",
      pendingSelfiePath: tempPath,
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
  },

  confirmSelfie() {
    if (!this.data.pendingSelfiePath) return;
    this.setData({
      imageTempPath: this.data.pendingSelfiePath,
      pendingSelfiePath: "",
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
  },

  async retakeSelfie() {
    this.setData({
      imageTempPath: "",
      pendingSelfiePath: "",
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
    await this.chooseSelfie();
  },

  cancelPendingSelfie() {
    this.setData({
      pendingSelfiePath: "",
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
  },

  clearImage() {
    this.setData({
      imageTempPath: "",
      pendingSelfiePath: "",
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
  },

  startRecord() {
    if (this.data.isRecording) return;

    this.setData({
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });

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
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
  },

  goHistory() {
    wx.navigateTo({ url: "/pages/history/index" });
  },

  goSettings() {
    wx.navigateTo({ url: "/pages/settings/index" });
  },

  async pollAnalyzeTaskResult(taskId, options = {}) {
    const pollStart = Date.now();
    const timeoutMs = Math.max(10000, Number(options.timeoutMs) || ANALYZE_POLL_TIMEOUT_MS);
    let pollIntervalMs = Math.max(300, Number(options.pollIntervalMs) || ANALYZE_POLL_DEFAULT_INTERVAL_MS);
    let transientErrorCount = 0;

    while (Date.now() - pollStart < timeoutMs) {
      try {
        const task = await getAnalyzeTask(taskId);
        transientErrorCount = 0;
        pollIntervalMs = Math.max(
          300,
          Number(task && task.poll_after_ms) || Number(options.pollIntervalMs) || ANALYZE_POLL_DEFAULT_INTERVAL_MS
        );
        const stageText = buildTaskStageText(task);
        this.setData({
          submitStage: SUBMIT_STAGE.ANALYZING,
          submitStatusText: stageText,
          submitButtonText: "分析中...",
          errorMsg: "",
        });

        const status = normalizeTaskStatus(task && task.status);
        if (status === "succeeded") {
          if (task && task.result) {
            return task.result;
          }
          throw new Error("分析任务已完成，但未返回结果。");
        }
        if (status === "failed") {
          const detail = ((task && task.error_detail) || "").trim();
          throw new Error(detail || "分析失败，请稍后重试。");
        }
      } catch (err) {
        transientErrorCount += 1;
        if (transientErrorCount > ANALYZE_POLL_TRANSIENT_RETRY_LIMIT) {
          throw err;
        }
        this.setData({
          submitStage: SUBMIT_STAGE.ANALYZING,
          submitStatusText: "结果查询中断，正在自动重试...",
          submitButtonText: "分析中...",
          errorMsg: "",
        });
      }

      await sleep(pollIntervalMs);
    }

    throw new Error("分析任务仍在处理中，请稍后再次点击“提交分析”继续查询，或到历史记录页查看结果。");
  },

  async submitAnalyze() {
    const text = (this.data.text || "").trim();
    const imageTempPath = this.data.imageTempPath;
    const pendingSelfiePath = this.data.pendingSelfiePath;
    const audioTempPath = this.data.audioTempPath;

    if (pendingSelfiePath && !imageTempPath) {
      this.setData({ errorMsg: "请先确认自拍照片，再提交分析。" });
      return;
    }

    if (!text && !imageTempPath && !audioTempPath) {
      this.setData({ errorMsg: "请至少提供文本、自拍或语音中的一种输入。" });
      return;
    }

    const audioValidation = await validateAudioBeforeUpload(audioTempPath, this.data.recordSeconds);
    if (!audioValidation.ok) {
      const guidance = `${audioValidation.message} 可重新录音，或清除语音后改用文字输入。`;
      this.setData({
        submitStage: SUBMIT_STAGE.FAILED,
        submitStatusText: `语音校验失败：${guidance}`,
        submitButtonText: "提交分析",
        errorMsg: guidance,
      });
      wx.showToast({
        title: "语音需重录",
        icon: "none",
      });
      return;
    }

    this.setData({
      isSubmitting: true,
      submitStage: SUBMIT_STAGE.UPLOADING,
      submitStatusText: "上传中：正在准备输入内容...",
      submitButtonText: "上传中...",
      errorMsg: "",
    });

    let submitSucceeded = false;
    try {
      let imageFileId = "";
      let imageTempUrl = "";
      let audioFileId = "";
      let audioTempUrl = "";

      const uploadLabel =
        imageTempPath && audioTempPath
          ? "上传中：正在上传自拍和语音..."
          : imageTempPath
            ? "上传中：正在上传自拍照片..."
            : audioTempPath
              ? "上传中：正在上传语音..."
              : "上传中：正在准备输入内容...";
      this.setData({
        submitStage: SUBMIT_STAGE.UPLOADING,
        submitStatusText: uploadLabel,
      });
      wx.showLoading({ title: "上传中..." });

      const uploadTasks = [];
      if (imageTempPath) {
        uploadTasks.push(
          (async () => {
            const preparedImage = await prepareImageForUpload(imageTempPath);
            const uploadedImage = await uploadTempFile(preparedImage.path, "images");
            imageFileId = (uploadedImage && uploadedImage.fileID) || "";
            imageTempUrl = (uploadedImage && uploadedImage.tempFileURL) || "";
          })()
        );
      }

      if (audioTempPath) {
        uploadTasks.push(
          (async () => {
            const uploadedAudio = await uploadTempFile(audioTempPath, "audio");
            audioFileId = (uploadedAudio && uploadedAudio.fileID) || "";
            audioTempUrl = (uploadedAudio && uploadedAudio.tempFileURL) || "";
          })()
        );
      }
      if (uploadTasks.length > 0) {
        await Promise.all(uploadTasks);
      }

      this.setData({
        submitStage: SUBMIT_STAGE.ANALYZING,
        submitStatusText: "分析中：正在生成情绪结果...",
        submitButtonText: "分析中...",
      });
      wx.showLoading({ title: "分析中..." });

      const buildAnalyzePayload = (includeAudio) => {
        const effectiveInputModes = [];
        if (text) effectiveInputModes.push("text");
        if (imageTempUrl || imageFileId) effectiveInputModes.push("selfie");
        if (includeAudio && (audioTempUrl || audioFileId)) effectiveInputModes.push("voice");

        const imagePayload =
          imageFileId || imageTempUrl
            ? {
                file_id: imageFileId || undefined,
                url: imageTempUrl || undefined,
              }
            : undefined;
        const audioPayload =
          includeAudio && (audioFileId || audioTempUrl)
            ? {
                file_id: audioFileId || undefined,
                url: audioTempUrl || undefined,
              }
            : undefined;

        return {
          input_modes: effectiveInputModes,
          text: text || undefined,
          image: imagePayload,
          audio: audioPayload,

          // Legacy fields kept until all clients migrate.
          image_url: imageTempUrl || undefined,
          image_file_id: imageFileId || undefined,
          audio_url: includeAudio ? audioTempUrl || undefined : undefined,
          audio_file_id: includeAudio ? audioFileId || undefined : undefined,
          client: {
            platform: "mp-weixin",
            version: "0.1.0",
          },
        };
      };

      let analyzeUsedAudio = !!(audioTempUrl || audioFileId);
      let effectivePayload = buildAnalyzePayload(analyzeUsedAudio);
      let result = null;
      const runAnalyzeOnce = async (payloadForAnalyze) => {
        let asyncCreate = null;
        try {
          asyncCreate = await createAnalyzeTask(payloadForAnalyze);
        } catch (err) {
          const rawMessage = ((err && err.message) || "").toLowerCase();
          const asyncApiUnavailable =
            rawMessage.includes("404") || rawMessage.includes("not found") || rawMessage.includes("501");
          if (!asyncApiUnavailable) {
            throw err;
          }
          // Backward compatibility: old backend without async endpoint.
          return analyze(payloadForAnalyze);
        }

        const taskId = ((asyncCreate && asyncCreate.task_id) || "").trim();
        if (!taskId) {
          return analyze(payloadForAnalyze);
        }

        this.setData({
          submitStage: SUBMIT_STAGE.ANALYZING,
          submitStatusText: buildTaskStageText(asyncCreate),
          submitButtonText: "分析中...",
          errorMsg: "",
        });
        return this.pollAnalyzeTaskResult(taskId, {
          pollIntervalMs: Number(asyncCreate && asyncCreate.poll_after_ms) || ANALYZE_POLL_DEFAULT_INTERVAL_MS,
          timeoutMs: ANALYZE_POLL_TIMEOUT_MS,
        });
      };

      try {
        result = await runAnalyzeOnce(effectivePayload);
      } catch (err) {
        const message = ((err && err.message) || "").trim();
        const voiceReject = message.includes("[VOICE_");
        const canFallbackToTextOnly = analyzeUsedAudio && !!text && voiceReject;
        if (!canFallbackToTextOnly) {
          throw err;
        }

        analyzeUsedAudio = false;
        effectivePayload = buildAnalyzePayload(false);
        this.setData({
          submitStage: SUBMIT_STAGE.ANALYZING,
          submitStatusText: "语音识别不稳定，已自动改用文字继续分析...",
          submitButtonText: "分析中...",
          errorMsg: "",
        });
        result = await runAnalyzeOnce(effectivePayload);
      }

      this.setData({
        submitStage: SUBMIT_STAGE.RENDERING,
        submitStatusText: "结果生成中：正在打开结果页...",
        submitButtonText: "结果生成中...",
      });
      wx.showLoading({ title: "结果生成中..." });

      const app = getApp();
      app.globalData.latestAnalyzeContext = {
        request: {
          text,
          input_modes: effectivePayload.input_modes || [],
          image:
            imageTempUrl || imageFileId
              ? { url: imageTempUrl, file_id: imageFileId }
              : undefined,
          audio:
            analyzeUsedAudio && (audioTempUrl || audioFileId)
              ? { url: audioTempUrl, file_id: audioFileId }
              : undefined,
          imageFileId,
          imageTempUrl,
          audioFileId: analyzeUsedAudio ? audioFileId : "",
          audioTempUrl: analyzeUsedAudio ? audioTempUrl : "",
          imageTempPath,
          audioTempPath: analyzeUsedAudio ? audioTempPath : "",
          uploadedAudioFileId: audioFileId,
          uploadedAudioTempUrl: audioTempUrl,
          uploadedAudioTempPath: audioTempPath,
          image_url: imageTempUrl,
          image_file_id: imageFileId,
          audio_url: analyzeUsedAudio ? audioTempUrl : "",
          audio_file_id: analyzeUsedAudio ? audioFileId : "",
          image_temp_path: imageTempPath,
          audio_temp_path: analyzeUsedAudio ? audioTempPath : "",
          uploaded_audio_file_id: audioFileId,
          uploaded_audio_url: audioTempUrl,
          uploaded_audio_temp_path: audioTempPath,
        },
        response: result,
      };

      submitSucceeded = true;
      wx.navigateTo({
        url: "/pages/result/result",
      });
    } catch (err) {
      const rawMessage = ((err && err.message) || "").trim();
      const isPendingProcessing = rawMessage.includes("分析任务仍在处理中");
      const errorMsg = buildRecoverableAnalyzeError(err);
      this.setData({
        submitStage: isPendingProcessing ? SUBMIT_STAGE.ANALYZING : SUBMIT_STAGE.FAILED,
        submitStatusText: isPendingProcessing
          ? "分析任务仍在处理，点击“提交分析”可继续查询结果。"
          : "分析失败：可直接重试，原输入已保留。",
        submitButtonText: "提交分析",
        errorMsg,
      });
      wx.showToast({
        title: isPendingProcessing ? "任务处理中" : "分析失败，可重试",
        icon: "none",
      });
    } finally {
      wx.hideLoading();
      this.setData({
        isSubmitting: false,
        submitStage: submitSucceeded ? SUBMIT_STAGE.IDLE : this.data.submitStage,
        submitStatusText: submitSucceeded ? "" : this.data.submitStatusText,
        submitButtonText: "提交分析",
      });
    }
  },
});
