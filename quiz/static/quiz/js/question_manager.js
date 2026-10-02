const typeInput = document.querySelector("#id_question_type");
const fieldsForChoices = ["choice_1", "choice_2", "choice_3", "choice_4", "correct_choice"];
const fieldsForAnswerText = ["correct_text"];
const fieldsForAudio = ["audio_file"];

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
}

typeInput.addEventListener("change", updateQuestionForm);
updateQuestionForm();
