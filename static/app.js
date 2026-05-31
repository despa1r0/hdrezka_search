const form = document.getElementById("searchForm");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const button = document.getElementById("submitBtn");

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

const renderItem = (item) => {
  const image = item.image
    ? `<img class="poster" src="${escapeHtml(item.image)}" alt="">`
    : "<div class=\"poster\"></div>";

  const rating = item.rating == null
    ? "<span class=\"rating\">нет рейтинга</span>"
    : `<span class="rating">${Number(item.rating).toFixed(1)} ${escapeHtml(item.ratingSource)}</span>`;

  const genres = item.genres?.length ? item.genres.join(", ") : "жанры не найдены";
  const countries = item.countries?.length ? item.countries.join(", ") : "страны не найдены";
  const year = item.year ? ` · ${item.year}` : "";

  return `
    <article class="card">
      ${image}
      <div class="meta">
        <a class="title" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
        ${rating}
        <div class="muted">${escapeHtml(item.category || "")}${escapeHtml(year)}</div>
        <div class="muted">${escapeHtml(genres)}</div>
        <div class="muted">${escapeHtml(countries)}</div>
      </div>
    </article>
  `;
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const params = new URLSearchParams(new FormData(form));
  button.disabled = true;
  resultsEl.innerHTML = "";
  setStatus("Идет поиск и добор рейтингов...");

  try {
    const response = await fetch(`/api/search?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Ошибка поиска");
    }

    resultsEl.innerHTML = data.items.map(renderItem).join("");
    setStatus(`Найдено: ${data.count}. Время: ${data.elapsed} сек.`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
});
