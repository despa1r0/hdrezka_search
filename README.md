# HdRezka Filter

Локальная страница поиска по HdRezka с сортировкой по рейтингу и бан-листом жанров/стран.

## Возможности

- поиск через `HdRezkaApi`;
- жанровые запросы вроде `фантастика` и `детектив` собираются из каталога фильмов, а не из коротких ajax-подсказок;
- добор жанров, стран, постера и оригинального названия со страницы тайтла;
- сортировка по IMDb-рейтингу;
- режим карточек и текстовый режим без изображений;
- пользовательский лимит результатов;
- фильтр минимального IMDb-рейтинга;
- включающие фильтры и бан-листы жанров/стран через запятую.

По жанровым запросам приложение по умолчанию собирает до 100 карточек до применения фильтров. Максимальный лимит в интерфейсе - 300.

## Запуск

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m pip install -r requirements.txt
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" main.py
```

После запуска открой:

```text
http://127.0.0.1:8000/
```

## Остановка сервера

Через интерфейс: кнопка `Остановить сервер`.

Через PowerShell:

```powershell
.\stop_server.ps1
```

Подробности по текущему состоянию и планам лежат в [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Структура

```text
app/
  clients/
    imdb.py          # IMDb fallback rating
    rezka.py         # Rezka search and metadata scraping
  services/
    search_service.py
  utils/
    text.py
  config.py
  models.py
  server.py
static/
  app.js
  styles.css
templates/
  index.html
main.py
requirements.txt
```
