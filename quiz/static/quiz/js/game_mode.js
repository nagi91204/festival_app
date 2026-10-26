const modeForm = document.querySelector(".setup-form");
if (modeForm) {
  const difficultyInputs = [...modeForm.querySelectorAll('input[name="difficulty"]')];
  const categoryInputs = [...modeForm.querySelectorAll('input[name="categories"]')];
  const allCategoriesButton = document.querySelector("#all-categories");
  const categoryHint = document.querySelector("#category-selection-hint");

  function refreshSelection() {
    difficultyInputs.forEach((input) => input.closest(".difficulty-card")?.classList.toggle("selected", input.checked));
    categoryInputs.forEach((input) => input.closest("label")?.classList.toggle("selected", input.checked));
    const selected = categoryInputs.filter((input) => input.checked).map((input) => input.value);
    allCategoriesButton?.classList.toggle("selected", !selected.length);
    allCategoriesButton?.setAttribute("aria-pressed", String(!selected.length));
    if (categoryHint) categoryHint.textContent = selected.length ? `選択中：${selected.join("・")}` : "全カテゴリから出題します";
  }

  [...difficultyInputs, ...categoryInputs].forEach((input) => input.addEventListener("change", refreshSelection));
  allCategoriesButton?.addEventListener("click", () => { categoryInputs.forEach((input) => { input.checked = false; }); refreshSelection(); });
}
