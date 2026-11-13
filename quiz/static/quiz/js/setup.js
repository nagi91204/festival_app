const form = document.querySelector(".setup-form");
if (form) {
  const stats = JSON.parse(document.querySelector("#question-stats")?.textContent || "[]");
  const categoryInputs = [...form.querySelectorAll('input[name="categories"]')];
  const allCategoriesButton = document.querySelector("#all-categories");
  const submitButton = form.querySelector('button[type="submit"]');
  const countLabel = document.querySelector("#available-count");
  const detail = document.querySelector("#availability-detail");
  const warning = document.querySelector("#setup-warning");
  const categoryHint = document.querySelector("#category-selection-hint");
  const teacherQuizCategory = "先生クイズ";

  function updatePreview() {
    const selectedCategories = categoryInputs.filter((input) => input.checked).map((input) => input.value);
    const matchingCount = stats
      .filter((item) => selectedCategories.length
        ? selectedCategories.includes(item.category)
        : item.category !== teacherQuizCategory)
      .reduce((sum, item) => sum + item.count, 0);
    const selectedLabel = selectedCategories.length ? `選択中：${selectedCategories.join("・")}` : "全カテゴリから出題します（先生クイズを除く）";

    categoryInputs.forEach((input) => {
      input.closest("label")?.classList.toggle("selected", input.checked);
      const categoryCount = stats.filter((item) => item.category === input.value).reduce((sum, item) => sum + item.count, 0);
      const countBadge = input.closest("label")?.querySelector(".category-count");
      if (countBadge) countBadge.textContent = `${categoryCount}`;
    });
    if (allCategoriesButton) {
      allCategoriesButton.classList.toggle("selected", !selectedCategories.length);
      allCategoriesButton.setAttribute("aria-pressed", String(!selectedCategories.length));
    }
    if (categoryHint) categoryHint.textContent = selectedLabel;
    if (matchingCount === 0) {
      countLabel.textContent = "該当する問題がありません";
      detail.textContent = "問題管理でこのカテゴリの問題を登録してください。";
      warning.classList.remove("hidden");
      warning.textContent = "条件に合う問題がないため、ゲームを作成できません。";
      submitButton.disabled = true;
    } else {
      countLabel.textContent = `この条件で ${matchingCount} 問を出題します`;
      detail.textContent = "時間内は何問でも出題できます。全問出題後はランダムに繰り返します。";
      warning.classList.add("hidden");
      submitButton.disabled = false;
    }
  }

  categoryInputs.forEach((input) => input.addEventListener("change", updatePreview));
  allCategoriesButton?.addEventListener("click", () => {
    categoryInputs.forEach((input) => { input.checked = false; });
    updatePreview();
  });
  updatePreview();
}

const joinInput = document.querySelector("#join-code-input");
const joinForm = document.querySelector(".join-form");
if (joinInput && joinForm) {
  joinInput.addEventListener("input", () => {
    joinInput.value = joinInput.value.replace(/\D/g, "").slice(0, 6);
    if (joinInput.value.length === 4 || joinInput.value.length === 6) joinForm.submit();
  });
}  
