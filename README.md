# HdRezka Filter

Локальная страница поиска по HdRezka с сортировкой по рейтингу и бан-листом жанров/стран.

## Возможности

- поиск через `HdRezkaApi`;
- жанровые запросы вроде `фантастика` и `детектив` собираются из каталога фильмов, а не из коротких ajax-подсказок;
- добор жанров, стран, постера и оригинального названия со страницы тайтла;
- сортировка по IMDb-рейтингу;
- режим карточек и текстовый режим без изображений;
- пользовательский лимит результатов;
- фильтр диапазона IMDb-рейтинга, например `8.0 - 5.0`;
- сортировка от высокой оценки к низкой и от низкой к высокой;
- включающие фильтры и бан-листы жанров/стран через запятую.

По жанровым запросам приложение пытается вернуть заданное число результатов после фильтров. Максимальный лимит в интерфейсе - 300.

## Запуск

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m pip install -r requirements.txt
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" main.py
```

После запуска открой:

```text
http://127.0.0.1:8000/
```

Для debug-логов запускай сервер прямо в терминале:

```powershell
$env:HDREZKA_DEBUG = "1"
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" main.py
```

Также можно включить чекбокс `Debug в терминал` в интерфейсе для конкретного запроса.

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
