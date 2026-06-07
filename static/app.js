const form = document.getElementById("searchForm");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const button = document.getElementById("submitBtn");
const crawlBtn = document.getElementById("crawlBtn");
const userSelect = document.getElementById("userSelect");
const sortModeSelect = document.getElementById("sortMode");
const themeToggle = document.getElementById("themeToggle");
const viewModeInputs = Array.from(document.querySelectorAll("input[name='view_mode']"));

let currentItems = [];
let lastSearchParams = null;
let lastResultMeta = null;
let crawlProgressTimer = null;

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

const applyTheme = (theme) => {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("hdrezka-theme", theme);
  } catch {
    // Theme still changes for the current page if storage is unavailable.
  }
  const dark = theme === "dark";
  themeToggle.checked = dark;
  themeToggle.setAttribute("aria-checked", String(dark));
};

const initTheme = () => {
  let saved = "";
  try {
    saved = localStorage.getItem("hdrezka-theme") || "";
  } catch {
    saved = "";
  }
  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
  applyTheme(saved || (prefersDark ? "dark" : "light"));
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

const selectedMode = () => {
  const selected = viewModeInputs.find((input) => input.checked);
  return selected?.value || "cards";
};

const paramsFromForm = () => {
  const formData = new FormData(form);
  formData.delete("view_mode");

  if (!formData.get("exclude_seen")) {
    formData.set("exclude_seen", "0");
  }

  return new URLSearchParams(formData);
};

const runSearch = async (params, mode, { clear = true } = {}) => {
  button.disabled = true;
  if (clear) {
    resultsEl.innerHTML = "";
  }
  setStatus("Ищу в локальной PostgreSQL-базе...");

  try {
    const response = await fetch(`/api/search?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Ошибка поиска");
    }

    currentItems = data.items;
    lastSearchParams = new URLSearchParams(params);
    lastResultMeta = data;
    renderResults(currentItems, mode);
    setStatus(`Найдено: ${data.count}. Источник рейтинга: IMDb. Время: ${data.elapsed} сек.`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
};

const startCrawlProgressPolling = () => {
  stopCrawlProgressPolling();
  crawlProgressTimer = setInterval(async () => {
    try {
      const response = await fetch("/api/crawl-progress");
      const data = await response.json();
      if (!response.ok) {
        return;
      }
      const stats = data.stats || {};
      const catalogLine = data.catalogUrl ? `\nКаталог: ${data.catalogUrl}` : "";
      const currentLine = data.url && data.url !== data.catalogUrl ? `\nТекущая ссылка: ${data.url}` : "";
      const counters = `Сохранено: ${stats.saved || 0}. Уже было: ${stats.existing || 0}. Пропущено: ${stats.skipped || 0}. Страниц: ${stats.pages || 0}.`;
      const message = data.error ? `${data.message || "Crawler ошибка"}: ${data.error}` : (data.message || "Crawler работает...");
      setStatus(`${message} ${counters}${catalogLine}${currentLine}`, Boolean(data.error));
      if (!data.running) {
        stopCrawlProgressPolling();
      }
    } catch {
      // Keep the main crawl request in charge of user-visible errors.
    }
  }, 900);
};

const stopCrawlProgressPolling = () => {
  if (crawlProgressTimer) {
    clearInterval(crawlProgressTimer);
    crawlProgressTimer = null;
  }
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

  const mode = selectedMode();
  const params = paramsFromForm();
  await runSearch(params, mode);
});

viewModeInputs.forEach((input) => {
  input.addEventListener("change", () => {
    renderResults(currentItems, selectedMode());
    if (lastResultMeta) {
      setStatus(`Найдено: ${lastResultMeta.count}. Источник рейтинга: IMDb. Время: ${lastResultMeta.elapsed} сек.`);
    }
  });
});

sortModeSelect.addEventListener("change", async () => {
  if (!lastSearchParams) {
    return;
  }
  const params = new URLSearchParams(lastSearchParams);
  params.set("sort_mode", sortModeSelect.value);
  await runSearch(params, selectedMode());
});

themeToggle.addEventListener("change", () => {
  applyTheme(themeToggle.checked ? "dark" : "light");
});

crawlBtn.addEventListener("click", async () => {
  crawlBtn.disabled = true;
  const crawlParams = paramsFromForm();
  setStatus("Дозагружаю подходящие фильмы Rezka в локальную БД...");
  startCrawlProgressPolling();

  try {
    const response = await fetch("/api/crawl", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(crawlParams)),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Crawler не смог дозагрузить фильмы");
    }

    const stats = data.stats || {};
    const hasErrors = Number(stats.errors || 0) > 0;
    const summary = hasErrors
      ? `Crawler закончил с ошибками: ${stats.last_error || "смотри crawl_log"}`
      : `Дозагружено новых: ${stats.saved || 0}. Уже было: ${stats.existing || 0}. Пропущено: ${stats.skipped || 0}. Страниц: ${stats.pages || 0}. Ошибок: ${stats.errors || 0}.`;
    setStatus(summary, hasErrors);
    if (lastSearchParams) {
      const refreshedParams = paramsFromForm();
      await runSearch(refreshedParams, selectedMode(), { clear: false });
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    stopCrawlProgressPolling();
    crawlBtn.disabled = false;
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
      currentItems = currentItems.filter((item) => String(item.movieId ?? item.id) !== String(movieId));
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

initTheme();
loadUsers();
