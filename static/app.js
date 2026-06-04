const form = document.getElementById("searchForm");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const button = document.getElementById("submitBtn");
const stopBtn = document.getElementById("stopBtn");
const userSelect = document.getElementById("userSelect");

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

const renderActions = (item) => {
  const id = Number(item.movieId ?? item.id);
  if (!id) {
    return "";
  }

  return `
    <div class="actions" data-movie-id="${id}">
      <button type="button" data-state="seen">Уже смотрел</button>
      <button type="button" data-state="hidden">Скрыть</button>
      <button type="button" data-state="favorite">В избранное</button>
      <button type="button" data-state="watchlist">Хочу посмотреть</button>
    </div>
  `;
};

const renderCardItem = (item) => {
  const image = item.image
    ? `<img class="poster" src="${escapeHtml(item.image)}" alt="">`
    : "<div class=\"poster\"></div>";
  const genres = item.genres?.length ? item.genres.join(", ") : "жанры не указаны";
  const countries = item.countries?.length ? item.countries.join(", ") : "страны не указаны";
  const year = item.year ? ` · ${item.year}` : "";

  return `
    <article class="card" data-result-id="${escapeHtml(item.movieId ?? item.id)}">
      ${image}
      <div class="meta">
        <a class="title" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
        ${renderRating(item)}
        <div class="muted">${escapeHtml(item.category || "")}${escapeHtml(year)}</div>
        <div class="muted">${escapeHtml(genres)}</div>
        <div class="muted">${escapeHtml(countries)}</div>
        ${renderActions(item)}
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
    <article class="text-row" data-result-id="${escapeHtml(item.movieId ?? item.id)}">
      <div class="text-title">
        <span>${index + 1}.</span>
        <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
      </div>
      <div class="muted">${escapeHtml(rating + year + genres + countries)}</div>
      ${renderActions(item)}
    </article>
  `;
};

const renderResults = (items, mode) => {
  resultsEl.className = mode === "text" ? "results text-list" : "results cards";
  resultsEl.innerHTML = items
    .map((item, index) => mode === "text" ? renderTextItem(item, index) : renderCardItem(item))
    .join("");
};

const loadUsers = async () => {
  try {
    const response = await fetch("/api/users");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Не удалось загрузить пользователей");
    }

    userSelect.innerHTML = data.users
      .map((user) => `<option value="${escapeHtml(user.id)}">${escapeHtml(user.display_name || user.username)}</option>`)
      .join("");
  } catch (error) {
    userSelect.innerHTML = "<option value=\"\">Нет подключения к БД</option>";
    setStatus(error.message, true);
  }
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(form);
  const mode = formData.get("view_mode") || "cards";
  formData.delete("view_mode");

  if (!formData.get("exclude_seen")) {
    formData.set("exclude_seen", "0");
  }

  const params = new URLSearchParams(formData);
  button.disabled = true;
  resultsEl.innerHTML = "";
  setStatus("Ищу в локальной PostgreSQL-базе...");

  try {
    const response = await fetch(`/api/search?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Ошибка поиска");
    }

    renderResults(data.items, mode);
    setStatus(`Найдено: ${data.count}. Источник рейтинга: IMDb. Время: ${data.elapsed} сек.`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
});

resultsEl.addEventListener("click", async (event) => {
  const actionButton = event.target.closest("button[data-state]");
  if (!actionButton) {
    return;
  }

  const actions = actionButton.closest(".actions");
  const result = actionButton.closest("[data-result-id]");
  const userId = userSelect.value;
  const movieId = actions?.dataset.movieId;
  const state = actionButton.dataset.state;

  if (!userId || !movieId || !state) {
    return;
  }

  actionButton.disabled = true;
  try {
    const response = await fetch("/api/movie-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        movie_id: movieId,
        state,
        action: "set",
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Не удалось обновить состояние");
    }

    if (state === "seen" || state === "hidden") {
      result?.remove();
      setStatus(state === "seen" ? "Фильм помечен как просмотренный." : "Фильм скрыт.");
    } else {
      actionButton.textContent = state === "favorite" ? "В избранном" : "В списке";
      setStatus(state === "favorite" ? "Добавлено в избранное." : "Добавлено в список просмотра.");
    }
  } catch (error) {
    actionButton.disabled = false;
    setStatus(error.message, true);
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

loadUsers();
