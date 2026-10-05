const form = document.querySelector(".setup-form");
if (form) {
  const stats = JSON.parse(document.querySelector("#question-stats")?.textContent || "[]");
  const difficultyInputs = [...form.querySelectorAll('input[name="difficulty"]')];
  const categoryInputs = [...form.querySelectorAll('input[name="categories"]')];
  const allCategoriesButton = document.querySelector("#all-categories");
  const countInput = form.querySelector('input[name="question_count"]');
  const submitButton = form.querySelector('button[type="submit"]');
  const countLabel = document.querySelector("#available-count");
  const detail = document.querySelector("#availability-detail");
  const warning = document.querySelector("#setup-warning");
  const categoryHint = document.querySelector("#category-selection-hint");

  function updatePreview() {
    const difficulty = difficultyInputs.find((input) => input.checked)?.value || "normal";
    const selectedCategories = categoryInputs.filter((input) => input.checked).map((input) => input.value);
    const matchingCount = stats
      .filter((item) => item.difficulty === difficulty && (!selectedCategories.length || selectedCategories.includes(item.category)))
      .reduce((sum, item) => sum + item.count, 0);
    const requestedCount = Math.max(1, Number.parseInt(countInput.value, 10) || 1);
    const selectedLabel = selectedCategories.length ? `選択中：${selectedCategories.join("・")}` : "全カテゴリから出題します";

    difficultyInputs.forEach((input) => input.closest(".difficulty-card")?.classList.toggle("selected", input.checked));
    categoryInputs.forEach((input) => {
      input.closest("label")?.classList.toggle("selected", input.checked);
      const categoryCount = stats.filter((item) => item.difficulty === difficulty && item.category === input.value).reduce((sum, item) => sum + item.count, 0);
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
      detail.textContent = "問題管理でこの難易度・カテゴリの問題を登録してください。";
      warning.classList.remove("hidden");
      warning.textContent = "条件に合う問題がないため、ゲームを作成できません。";
      submitButton.disabled = true;
    } else {
      const actualCount = Math.min(matchingCount, requestedCount);
      countLabel.textContent = `この条件で最大 ${actualCount} 問`;
      detail.textContent = matchingCount < requestedCount ? `登録済みは${matchingCount}問です。出題数は登録数に合わせます。` : `${matchingCount}問からランダムに出題します。`;
      warning.classList.add("hidden");
      submitButton.disabled = false;
    }
  }

  [...difficultyInputs, ...categoryInputs, countInput].forEach((input) => input.addEventListener("change", updatePreview));
  countInput.addEventListener("input", updatePreview);
  allCategoriesButton?.addEventListener("click", () => {
    categoryInputs.forEach((input) => { input.checked = false; });
    updatePreview();
  });
  updatePreview();
}
