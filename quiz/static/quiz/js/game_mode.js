const modeForm = document.querySelector(".setup-form");
if (modeForm) {
  const categoryInputs = [...modeForm.querySelectorAll('input[name="categories"]')];
  const allCategoriesButton = document.querySelector("#all-categories");
  const categoryHint = document.querySelector("#category-selection-hint");

  function refreshSelection() {
    categoryInputs.forEach((input) => input.closest("label")?.classList.toggle("selected", input.checked));
    const selected = categoryInputs.filter((input) => input.checked).map((input) => input.value);
    allCategoriesButton?.classList.toggle("selected", !selected.length);
    allCategoriesButton?.setAttribute("aria-pressed", String(!selected.length));
    if (categoryHint) categoryHint.textContent = selected.length ? `選択中：${selected.join("・")}` : "全カテゴリから出題します（先生クイズを除く）";
  }

  categoryInputs.forEach((input) => input.addEventListener("change", refreshSelection));
  allCategoriesButton?.addEventListener("click", () => { categoryInputs.forEach((input) => { input.checked = false; }); refreshSelection(); });
}
