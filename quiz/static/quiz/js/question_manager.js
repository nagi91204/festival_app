const typeInput = document.querySelector("#id_question_type");
const fieldsForChoices = ["choice_1", "choice_2", "choice_3", "choice_4", "correct_choice"];
const fieldsForAnswerText = ["correct_text"];
const fieldsForAudio = ["audio_file"];
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
  const type = questionElement.dataset.type || "choice";
  const title = questionElement.querySelector("strong").textContent;
  const body = questionElement.querySelector("p").textContent;
  const category = questionElement.querySelector("small").textContent.split(" / ")[0];
  const imageUrl = questionElement.dataset.imageUrl || "";
  const audioUrl = questionElement.dataset.audioUrl || "";
  const choices = JSON.parse(questionElement.dataset.choices || "[]");
  const correctChoice = parseInt(questionElement.dataset.correctChoice || "1");
  const correctText = questionElement.dataset.correctText || "";
  const explanation = questionElement.dataset.explanation || "";
  return { type, title, body, category, imageUrl, audioUrl, choices, correctChoice, correctText, explanation };
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

function renderPreview() {
  if (!currentQuestionData) return;
  const data = currentQuestionData;
  const typeName = { choice: "2択・4択問題", buzzer: "早押し問題", audio: "音当て問題", image: "画像予想問題" }[data.type] || "クイズ";

  // Stop audio when leaving question phase
  if (previewState !== "question") {
    stopPreviewAudio();
    const existingBtn = document.querySelector("#preview-audio-btn");
    if (existingBtn) existingBtn.remove();
  }

  if (previewState === "intro") {
    previewPhase.textContent = `次は「${typeName}」です！`;
    previewMeta.textContent = "QUESTION 1 / 10";
    previewBody.textContent = "";
    previewImage.classList.add("hidden");
    previewImage.src = "";
    previewChoices.innerHTML = "";
    previewAnswer.classList.add("hidden");
  } else if (previewState === "question") {
    previewPhase.textContent = "問題・回答中";
    previewMeta.textContent = "QUESTION 1 / 10";
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
  } else if (previewState === "result") {
    previewPhase.textContent = "結果発表";
    previewMeta.textContent = "QUESTION 1 / 10";
    previewBody.textContent = data.body || "問題文がここに表示されます";
    if (data.type === "choice" || data.type === "image") {
      previewChoices.innerHTML = data.choices.map((text, i) =>
        `<span class="choice${i + 1 === data.correctChoice ? " correct" : ""}">${i + 1}. ${escapeHtml(text)}</span>`
      ).join("");
    }
    previewAnswer.textContent = `正解：${data.correctText}${data.explanation ? " / " + data.explanation : ""}`;
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
