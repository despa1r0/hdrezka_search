# HdRezka Filter

Локальная страница поиска по HdRezka с сортировкой по рейтингу и бан-листом жанров/стран.

## Возможности

- поиск через `HdRezkaApi`;
- жанровые запросы вроде `фантастика` и `детектив` собираются из каталога фильмов, а не из коротких ajax-подсказок;
- добор жанров, стран, постера и оригинального названия со страницы тайтла;
- сортировка по рейтингу Rezka;
- fallback на IMDb-рейтинг, если у результата нет рейтинга Rezka;
- бан-лист жанров и стран через запятую.

По жанровым запросам приложение собирает минимум 100 карточек до применения бан-листов.

## Запуск

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m pip install -r requirements.txt
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" main.py
```

После запуска открой:

```text
http://127.0.0.1:8000/
```

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
