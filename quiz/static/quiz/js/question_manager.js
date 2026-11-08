const typeInput = document.querySelector("#id_question_type");
const fieldsForChoices = ["choice_1", "choice_2", "choice_3", "choice_4", "correct_choice"];
const fieldsForAnswerText = ["correct_text"];
const fieldsForAudio = ["audio_file"];
const fieldsForVideo = ["video_file"];
const fieldsForImage = ["image"];

function setFieldVisibility(names, visible) {
  names.forEach((name) => {
    const field = document.querySelector(`[data-field="${name}"]`);
    if (field) field.classList.toggle("hidden", !visible);
  });
}

function updateQuestionForm() {
  const type = typeInput.value;
  setFieldVisibility(fieldsForChoices, type === "choice");
  setFieldVisibility(fieldsForAnswerText, type !== "choice");
  setFieldVisibility(fieldsForAudio, type === "audio");
  setFieldVisibility(fieldsForVideo, type === "video");
  setFieldVisibility(fieldsForImage, type === "image");
}

typeInput.addEventListener("change", updateQuestionForm);
updateQuestionForm();

// Preview Modal functionality
const previewModal = document.querySelector("#preview-modal");
const previewClose = document.querySelector("#preview-close");
const previewOverlay = document.querySelector(".preview-modal-overlay");
const previewPhase = document.querySelector("#preview-phase");
const previewMeta = document.querySelector("#preview-meta");
const previewBody = document.querySelector("#preview-body");
const previewImage = document.querySelector("#preview-image");
const previewVideo = document.querySelector("#preview-video");
const previewChoices = document.querySelector("#preview-choices");
const previewAnswer = document.querySelector("#preview-answer");

let previewState = "intro";
let currentQuestionData = null;
let previewAudio = null;

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function getQuestionData(questionElement) {
  const ds = questionElement.dataset;
  return {
    type: ds.type || "choice",
    number: parseInt(ds.number || "1", 10),
    total: parseInt(ds.total || "1", 10),
    title: ds.title || "",
    body: ds.body || "",
    imageUrl: ds.imageUrl || "",
    audioUrl: ds.audioUrl || "",
    videoUrl: ds.videoUrl || "",
    choices: JSON.parse(ds.choices || "[]"),
    correctChoice: parseInt(ds.correctChoice || "1", 10),
    correctText: ds.correctText || "",
    explanation: ds.explanation || "",
  };
}

function stopPreviewAudio() {
  if (previewAudio) {
    previewAudio.pause();
    previewAudio.src = "";
    previewAudio = null;
  }
}

function tryAutoPlayAudio(audioUrl) {
  if (!audioUrl) return;
  stopPreviewAudio();
  previewAudio = new Audio(audioUrl);
  const playPromise = previewAudio.play();
  if (playPromise !== undefined) {
    playPromise.catch(() => {
      // Autoplay blocked - show play button
      showAudioPlayButton(audioUrl);
    });
  }
}

function showAudioPlayButton(audioUrl) {
  const existingBtn = document.querySelector("#preview-audio-btn");
  if (existingBtn) return;
  const btn = document.createElement("button");
  btn.id = "preview-audio-btn";
  btn.className = "preview-audio-btn";
  btn.textContent = "▶ 音声を再生";
  btn.onclick = () => {
    stopPreviewAudio();
    previewAudio = new Audio(audioUrl);
    previewAudio.play().catch(() => {});
    btn.remove();
  };
  previewChoices.parentNode.insertBefore(btn, previewChoices.nextSibling);
}

function stopPreviewVideo() {
  previewVideo.pause();
  previewVideo.src = "";
  previewVideo.classList.add("hidden");
}

function tryAutoPlayVideo(videoUrl) {
  if (!videoUrl) return;
  previewVideo.src = videoUrl;
  previewVideo.classList.remove("hidden");
  const playPromise = previewVideo.play();
  if (playPromise !== undefined) {
    playPromise.catch(() => {
      // 自動再生が拒否された場合は再生ボタンを表示する
      showVideoPlayButton(videoUrl);
    });
  }
}

function showVideoPlayButton(videoUrl) {
  const existingBtn = document.querySelector("#preview-video-btn");
  if (existingBtn) return;
  const btn = document.createElement("button");
  btn.id = "preview-video-btn";
  btn.className = "preview-audio-btn";
  btn.textContent = "▶ 動画を再生";
  btn.onclick = () => {
    previewVideo.src = videoUrl;
    previewVideo.classList.remove("hidden");
    previewVideo.play().catch(() => {});
    btn.remove();
  };
  previewChoices.parentNode.insertBefore(btn, previewChoices.nextSibling);
}

function renderPreview() {
  if (!currentQuestionData) return;
  const data = currentQuestionData;
  const meta = `QUESTION ${data.number} / ${data.total}`;
  const typeName = { choice: "2択・4択問題", buzzer: "早押し問題", audio: "音当て問題", video: "動画当て問題", image: "画像予想問題" }[data.type] || "クイズ";

  // Stop audio when leaving question phase
  if (previewState !== "question") {
    stopPreviewAudio();
    const existingBtn = document.querySelector("#preview-audio-btn");
    if (existingBtn) existingBtn.remove();
    stopPreviewVideo();
    const existingVideoBtn = document.querySelector("#preview-video-btn");
    if (existingVideoBtn) existingVideoBtn.remove();
  }

  if (previewState === "intro") {
    previewPhase.textContent = `次は「${typeName}」です！`;
    previewMeta.textContent = meta;
    previewBody.textContent = "";
    previewImage.classList.add("hidden");
    previewImage.src = "";
    previewChoices.innerHTML = "";
    previewAnswer.classList.add("hidden");
  } else if (previewState === "question") {
    previewPhase.textContent = "問題・回答中";
    previewMeta.textContent = meta;
    previewBody.textContent = data.body || "問題文がここに表示されます";
    if (data.imageUrl) {
      previewImage.src = data.imageUrl;
      previewImage.classList.remove("hidden");
    } else {
      previewImage.classList.add("hidden");
    }
    if (data.type === "choice" || data.type === "image") {
      previewChoices.innerHTML = data.choices.map((text, i) =>
        `<span class="choice">${i + 1}. ${escapeHtml(text)}</span>`
      ).join("");
    } else {
      previewChoices.innerHTML = "";
    }
    previewAnswer.classList.add("hidden");
    // Try auto-play audio for AUDIO type questions
    if (data.type === "audio" && data.audioUrl) {
      tryAutoPlayAudio(data.audioUrl);
    }
    // Try auto-play video for VIDEO type questions
    if (data.type === "video" && data.videoUrl) {
      tryAutoPlayVideo(data.videoUrl);
    } else {
      stopPreviewVideo();
    }
  } else if (previewState === "result") {
    previewPhase.textContent = "結果発表";
    previewMeta.textContent = meta;
    previewBody.textContent = data.body || "問題文がここに表示されます";
    if (data.type === "choice" || data.type === "image") {
      previewChoices.innerHTML = data.choices.map((text, i) =>
        `<span class="choice${i + 1 === data.correctChoice ? " correct" : ""}">${i + 1}. ${escapeHtml(text)}</span>`
      ).join("");
    }
    const correctAnswer = data.correctText || data.choices[data.correctChoice - 1] || "";
    previewAnswer.textContent = `正解：${correctAnswer}${data.explanation ? " / " + data.explanation : ""}`;
    previewAnswer.classList.remove("hidden");
  }
}

function openPreview(questionElement) {
  currentQuestionData = getQuestionData(questionElement);
  previewState = "intro";
  renderPreview();
  previewModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closePreview() {
  previewModal.classList.add("hidden");
  document.body.style.overflow = "";
  currentQuestionData = null;
  stopPreviewAudio();
  const existingBtn = document.querySelector("#preview-audio-btn");
  if (existingBtn) existingBtn.remove();
  stopPreviewVideo();
  const existingVideoBtn = document.querySelector("#preview-video-btn");
  if (existingVideoBtn) existingVideoBtn.remove();
}

function cyclePreview() {
  previewState = ["intro", "question", "result"][(["intro", "question", "result"].indexOf(previewState) + 1) % 3];
  renderPreview();
}

// Event listeners
document.querySelectorAll(".preview-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const row = btn.closest(".question-list-row");
    openPreview(row);
  });
});

previewClose.addEventListener("click", closePreview);
previewOverlay.addEventListener("click", closePreview);
previewModal.addEventListener("click", (e) => {
  if (e.target === previewModal || e.target.closest(".preview-screen")) {
    cyclePreview();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !previewModal.classList.contains("hidden")) {
    closePreview();
  }
});
