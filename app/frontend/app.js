const form = document.getElementById("form");
const queryInput = document.getElementById("query");
const submitButton = document.getElementById("submit");
const resultBlock = document.getElementById("result");
const originalEl = document.getElementById("original");
const correctedEl = document.getElementById("corrected");
const errorEl = document.getElementById("error");

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
  resultBlock.hidden = true;
}

function renderResult(data) {
  errorEl.hidden = true;
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query) return;

  submitButton.disabled = true;
  try {
    const response = await fetch("/api/correct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || "Не удалось обработать запрос");
      return;
    }
    renderResult(data);
  } catch (err) {
    showError("Сеть недоступна: " + err.message);
  } finally {
    submitButton.disabled = false;
  }
});
