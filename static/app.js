const form = document.getElementById("searchForm");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const button = document.getElementById("submitBtn");
const crawlBtn = document.getElementById("crawlBtn");
const userSelect = document.getElementById("userSelect");
const sortModeSelect = document.getElementById("sortMode");
const themeToggle = document.getElementById("themeToggle");
const menuToggle = document.getElementById("menuToggle");
const menuPanel = document.getElementById("menuPanel");
const sectionMenu = document.getElementById("sectionMenu");
const sectionButtons = Array.from(document.querySelectorAll("[data-state-filter]"));
const viewModeInputs = Array.from(document.querySelectorAll("input[name='view_mode']"));

let currentItems = [];
let lastSearchParams = null;
let lastResultMeta = null;
let crawlProgressTimer = null;
let currentStateFilter = "all";

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

const itemHasState = (item, state) => Array.isArray(item.states) && item.states.includes(state);

const renderActions = (item) => {
  const id = Number(item.movieId ?? item.id);
  if (!id) {
    return "";
  }
  const seenActive = item.isSeen || itemHasState(item, "seen") ? " is-active" : "";
  const favoriteActive = item.isFavorite || itemHasState(item, "favorite") ? " is-active" : "";
  const watchlistActive = itemHasState(item, "watchlist") ? " is-active" : "";

  return `
    <div class="actions" data-movie-id="${id}">
      <button class="${seenActive}" type="button" data-state="seen">${item.isSeen ? "Просмотрен" : "Уже смотрел"}</button>
      <button type="button" data-state="hidden">Скрыть</button>
      <button class="${favoriteActive}" type="button" data-state="favorite">${item.isFavorite ? "Понравился" : "Понравился"}</button>
      <button class="${watchlistActive}" type="button" data-state="watchlist">${itemHasState(item, "watchlist") ? "В списке" : "Хочу посмотреть"}</button>
    </div>
  `;
};

const renderTitle = (item, className = "title") => `
  <div class="title-line">
    <a class="${className}" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
    <button class="copy-title" type="button" data-copy-title="${escapeHtml(item.title)}" title="Скопировать название" aria-label="Скопировать название">Copy</button>
  </div>
`;

const renderCardItem = (item) => {
  const image = item.image
    ? `<img class="poster" src="${escapeHtml(item.image)}" alt="">`
    : "<div class=\"poster\"></div>";
  const genres = item.genres?.length ? item.genres.join(", ") : "жанры не указаны";
  const countries = item.countries?.length ? item.countries.join(", ") : "страны не указаны";
  const year = item.year ? ` · ${item.year}` : "";
  const seenClass = item.isSeen ? " is-seen" : "";

  return `
    <article class="card${seenClass}" data-result-id="${escapeHtml(item.movieId ?? item.id)}">
      ${image}
      <div class="meta">
        ${renderTitle(item)}
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
  const seenClass = item.isSeen ? " is-seen" : "";

  return `
    <article class="text-row${seenClass}" data-result-id="${escapeHtml(item.movieId ?? item.id)}">
      <div class="text-title">
        <span>${index + 1}.</span>
        ${renderTitle(item, "")}
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
  formData.set("state_filter", currentStateFilter);

  if (!formData.get("exclude_seen")) {
    formData.set("exclude_seen", "0");
  }
  if (!formData.get("include_seen")) {
    formData.set("include_seen", "0");
  }

  return new URLSearchParams(formData);
};

const sectionLabel = () => {
  const active = sectionButtons.find((item) => item.dataset.stateFilter === currentStateFilter);
  return active?.textContent?.trim() || "Все фильмы";
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
    setStatus(`${sectionLabel()}. Найдено: ${data.count}. Источник рейтинга: IMDb. Время: ${data.elapsed} сек.`);
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
      setStatus(`${sectionLabel()}. Найдено: ${lastResultMeta.count}. Источник рейтинга: IMDb. Время: ${lastResultMeta.elapsed} сек.`);
    }
  });
});

const closeMenu = () => {
  menuPanel.hidden = true;
  menuToggle.setAttribute("aria-expanded", "false");
};

const setActiveSection = async (stateFilter) => {
  currentStateFilter = stateFilter;
  sectionButtons.forEach((item) => {
    const active = item.dataset.stateFilter === currentStateFilter;
    item.toggleAttribute("aria-current", active);
  });
  closeMenu();
  if (userSelect.value) {
    await runSearch(paramsFromForm(), selectedMode());
  }
};

menuToggle.addEventListener("click", () => {
  const open = menuPanel.hidden;
  menuPanel.hidden = !open;
  menuToggle.setAttribute("aria-expanded", String(open));
});

menuPanel.addEventListener("click", async (event) => {
  const item = event.target.closest("[data-state-filter]");
  if (!item) {
    return;
  }
  await setActiveSection(item.dataset.stateFilter || "all");
});

document.addEventListener("click", (event) => {
  if (!sectionMenu.contains(event.target)) {
    closeMenu();
  }
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
  const copyButton = event.target.closest("button[data-copy-title]");
  if (copyButton) {
    await copyTitle(copyButton.dataset.copyTitle || "");
    return;
  }

  const actionButton = event.target.closest("button[data-state]");
  if (!actionButton) {
    return;
  }

  const actions = actionButton.closest(".actions");
  const result = actionButton.closest("[data-result-id]");
  const userId = userSelect.value;
  const movieId = actions?.dataset.movieId;
  const state = actionButton.dataset.state;
  const action = state !== "hidden" && actionButton.classList.contains("is-active") ? "remove" : "set";

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
        action,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Не удалось обновить состояние");
    }

    if (state === "hidden") {
      result?.remove();
      currentItems = currentItems.filter((item) => String(item.movieId ?? item.id) !== String(movieId));
      setStatus("Фильм скрыт.");
    } else {
      const enabled = action === "set";
      markCurrentItemState(movieId, state, enabled);
      if (!enabled && currentStateFilter === state) {
        result?.remove();
        currentItems = currentItems.filter((item) => String(item.movieId ?? item.id) !== String(movieId));
        setStatus(state === "seen" ? "Метка просмотренного снята." : "Убрано из любимых.");
        return;
      }
      if (result) {
        result.classList.toggle("is-seen", state === "seen" ? enabled : result.classList.contains("is-seen"));
      }
      actionButton.classList.toggle("is-active", enabled);
      actionButton.textContent = stateButtonText(state, enabled);
      actionButton.disabled = false;
      setStatus(stateStatusText(state, enabled));
    }
  } catch (error) {
    actionButton.disabled = false;
    setStatus(error.message, true);
  }
});

const markCurrentItemState = (movieId, state, enabled) => {
  currentItems = currentItems.map((item) => {
    if (String(item.movieId ?? item.id) !== String(movieId)) {
      return item;
    }
    const states = Array.isArray(item.states) ? item.states : [];
    const nextStates = enabled
      ? (states.includes(state) ? states : [...states, state])
      : states.filter((itemState) => itemState !== state);
    return {
      ...item,
      states: nextStates,
      isSeen: nextStates.includes("seen"),
      isFavorite: nextStates.includes("favorite"),
    };
  });
};

const stateButtonText = (state, enabled) => {
  if (state === "seen") {
    return enabled ? "Просмотрен" : "Уже смотрел";
  }
  if (state === "favorite") {
    return "Понравился";
  }
  if (state === "watchlist") {
    return enabled ? "В списке" : "Хочу посмотреть";
  }
  return enabled ? "Добавлено" : "Добавить";
};

const stateStatusText = (state, enabled) => {
  if (state === "seen") {
    return enabled ? "Фильм помечен как просмотренный." : "Метка просмотренного снята.";
  }
  if (state === "favorite") {
    return enabled ? "Добавлено в любимые." : "Убрано из любимых.";
  }
  if (state === "watchlist") {
    return enabled ? "Добавлено в список просмотра." : "Убрано из списка просмотра.";
  }
  return enabled ? "Метка добавлена." : "Метка снята.";
};

const copyTitle = async (title) => {
  if (!title) {
    return;
  }
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(title);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = title;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    setStatus(`Название скопировано: ${title}`);
  } catch {
    setStatus("Не удалось скопировать название.", true);
  }
};

initTheme();
loadUsers();
