const form = document.getElementById("form");
const queryInput = document.getElementById("query");
const submitButton = document.getElementById("submit");
const resultBlock = document.getElementById("result");
const originalEl = document.getElementById("original");
const correctedEl = document.getElementById("corrected");
const categoriesBlock = document.getElementById("categories");
const categoryList = document.getElementById("category-list");
const errorEl = document.getElementById("error");

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
  resultBlock.hidden = true;
  categoriesBlock.hidden = true;
}

function renderCorrection(data) {
  originalEl.textContent = data.original;
  correctedEl.replaceChildren();
  data.words.forEach((word, index) => {
    if (index > 0) correctedEl.append(" ");
    const span = document.createElement("span");
    span.textContent = word.corrected;
    if (word.changed) span.className = "word-changed";
    correctedEl.append(span);
  });
  resultBlock.hidden = false;
}

function renderCategories(categories) {
  categoryList.replaceChildren();
  categories.forEach((cat, index) => {
    const li = document.createElement("li");
    li.className = index === 0 ? "category category-main" : "category";
    const name = document.createElement("span");
    name.className = "category-name";
    name.textContent = cat.name;
    const score = document.createElement("span");
    score.className = "category-score";
    score.textContent = Math.round(cat.score * 100) + "%";
    li.append(name, score);
    categoryList.append(li);
  });
  categoriesBlock.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query) return;

  submitButton.disabled = true;
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || "Не удалось обработать запрос");
      return;
    }
    errorEl.hidden = true;
    renderCorrection(data);
    renderCategories(data.categories);
  } catch (err) {
    showError("Сеть недоступна: " + err.message);
  } finally {
    submitButton.disabled = false;
  }
});
