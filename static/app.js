const form = document.getElementById("searchForm");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const button = document.getElementById("submitBtn");
const stopBtn = document.getElementById("stopBtn");

const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  "\"": "&quot;",
  "'": "&#39;",
}[char]));

const setStatus = (text, isError = false) => {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", isError);
};

const renderRating = (item) => {
  if (item.rating == null) {
    return "<span class=\"rating empty\">IMDb: нет оценки</span>";
  }
  return `<span class="rating">IMDb ${Number(item.rating).toFixed(1)}</span>`;
};

const renderCardItem = (item) => {
  const image = item.image
    ? `<img class="poster" src="${escapeHtml(item.image)}" alt="">`
    : "<div class=\"poster\"></div>";
  const genres = item.genres?.length ? item.genres.join(", ") : "жанры не найдены";
  const countries = item.countries?.length ? item.countries.join(", ") : "страны не найдены";
  const year = item.year ? ` · ${item.year}` : "";

  return `
    <article class="card">
      ${image}
      <div class="meta">
        <a class="title" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
        ${renderRating(item)}
        <div class="muted">${escapeHtml(item.category || "")}${escapeHtml(year)}</div>
        <div class="muted">${escapeHtml(genres)}</div>
        <div class="muted">${escapeHtml(countries)}</div>
      </div>
    </article>
  `;
};

const renderTextItem = (item, index) => {
  const rating = item.rating == null ? "IMDb: нет оценки" : `IMDb ${Number(item.rating).toFixed(1)}`;
  const year = item.year ? `, ${item.year}` : "";
  const genres = item.genres?.length ? ` | ${item.genres.join(", ")}` : "";
  const countries = item.countries?.length ? ` | ${item.countries.join(", ")}` : "";

  return `
    <article class="text-row">
      <div class="text-title">
        <span>${index + 1}.</span>
        <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
      </div>
      <div class="muted">${escapeHtml(rating + year + genres + countries)}</div>
    </article>
  `;
};

const renderResults = (items, mode) => {
  resultsEl.className = mode === "text" ? "results text-list" : "results cards";
  resultsEl.innerHTML = items
    .map((item, index) => mode === "text" ? renderTextItem(item, index) : renderCardItem(item))
    .join("");
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(form);
  const mode = formData.get("view_mode") || "cards";
  formData.delete("view_mode");

  const params = new URLSearchParams(formData);
  button.disabled = true;
  resultsEl.innerHTML = "";
  setStatus("Идет поиск и добор IMDb-рейтингов...");

  try {
    const response = await fetch(`/api/search?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Ошибка поиска");
    }

    renderResults(data.items, mode);
    setStatus(`Найдено: ${data.count}. Рейтинг: IMDb. Время: ${data.elapsed} сек.`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
});

stopBtn.addEventListener("click", async () => {
  stopBtn.disabled = true;
  setStatus("Останавливаю локальный сервер...");

  try {
    await fetch("/api/shutdown", { method: "POST" });
    setStatus("Сервер остановлен. Эту вкладку можно закрыть.");
  } catch (error) {
    setStatus("Сервер остановлен или соединение уже закрыто.");
  }
});
