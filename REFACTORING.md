# ZeroProblems (Hackaton_Backend) — заметки по рефакторингу

Документ составлен по состоянию репозитория на июнь 2026. Цель — безопасно развивать проект, не ломая демо и прод на Docker + OneDrive.

---

## 1. Краткая архитектура

```
Excel upload → pipeline (ONNX) → cache/{task_id}/labeled.parquet + report.json
                                      ↓
                              incident_store → Postgres (stored_jobs, stored_incidents)
                                      ↓
                              API (src/main.py) → React frontend

Параллельный канал:
/submit → complaint_submit → live0000 (Postgres) → live_report → dashboard / operator / map
```

| Область | Ключевые файлы |
|---------|----------------|
| API, роуты | `src/main.py` (~1200 строк) |
| Задачи на диске | `src/jobs.py`, `cache/` |
| Бизнес-логика | `app/pipeline.py`, `app/report.py`, `app/aggregate.py` |
| Postgres | `app/db/models.py`, `app/db/repository.py` |
| Live-поток | `app/live_stream.py`, `app/live_report.py`, `app/complaint_submit.py` |
| Геокод | `app/geocode.py`, `app/geocode_worker.py`, `app/db/geocode_cache_repo.py` |
| Инциденты (API) | `app/task_incidents.py` + дублирование в `repository.py` |
| Frontend | `frontend/src/App.jsx`, экраны в `screens/`, `api/client.js` |
| Docker | `docker-compose.yml`, `docker-compose.nominatim.yml`, `nginx/` |

---

## 2. Что важно не сломать (критические инварианты)

### 2.1 Live-поток `live0000`

- **ID задачи:** `live0000` — зашит в `app/live_stream.py`, `frontend/src/constants.js`. Менять только синхронно backend + frontend + миграция БД.
- **Префикс обращений:** `citizen-{12 hex}` — удаление, фильтрация live, UI (`isCitizenRowId` в `incidentModel.js`). Excel-строки имеют числовые `row_id` и **не удаляются** через live API.
- **Отчёты live** строятся из Postgres (`app/live_report.py`), **не** из `cache/live0000/`. Любой эндпоинт с `_require_completed()` без ветки `_is_live_task()` снова даст «Задача не найдена».
- **`ensure_live_stream_job()`** должен вызываться до операций с live (архив, submit, отчёты).

### 2.2 Двойное хранение задач

Система одновременно использует:

1. **Disk cache** — `cache/{task_id}/` (job_status.json, labeled.parquet, report.json)
2. **Postgres** — `stored_jobs`, `stored_incidents`

Правила:

- Excel после pipeline → сначала disk, потом `incident_store.persist_task_to_db`
- Live → только Postgres
- `jobs.get_report(task_id)` — единая точка: live → DB, иначе disk → fallback stored report
- Удаление из архива (`delete_stored_job`) **не** трогает cache и наоборот

### 2.3 Геокодирование

#### Хранение кэша

- **Основной кэш:** таблица Postgres/SQLite `geocode_cache` (`app/db/geocode_cache_repo.py`, модель `GeocodeCacheEntry`)
- **Legacy:** `data/geocode_cache.json` — однократный импорт через `import_json_cache_file()`, не основной путь
- **OneDrive/Windows:** запись в `./data` часто read-only → для legacy JSON fallback `/tmp/zeroproblems/geocode_cache.json` в `app/geocode.py`
- Ключ кэша: `normalize_address_key()` = `strip().lower()`

#### Nominatim

Только **локальный** Nominatim (Омская обл.): `http://nominatim:8080`, порт хоста `8088`. Публичный OSM API не используется.

Сервисы `nominatim` / `nominatim-pbf` встроены в `docker-compose.yml`.

Переменные (см. `.env.example`): `NOMINATIM_URL`, `NOMINATIM_MIN_INTERVAL_SEC`, `NOMINATIM_CONCURRENCY`, `GEOCODE_WARMUP_BATCH`.

#### Нормализация и viewbox

- `_nominatim_search_query()` — убирает `ул./д./Омская область` из строк выгрузки
- Viewbox Омска: `OMSK_CITY_VIEWBOX` + `bounded=1` — без этого ул. Ленина уезжает в Полтавку

#### Фоновый warmup

- Worker: `app/geocode_worker.py`; API: `/jobs/{task_id}/geocode/warmup`
- UI: `GeocodeWarmupButton.jsx` — прогресс ≤100% (по БД, не по retry-счётчику)
- Адреса с `geocode_cache.failed=true` **не ретраятся** в warmup (`fetch_pending_address_lines`)
- Параллельный Nominatim: `ThreadPoolExecutor` + пакетный `get_geocode_many()`

#### Карта vs список

- `GET /jobs/{id}/incidents` — полные карточки, limit до 5000
- `GET /jobs/{id}/incidents/map-markers` — лёгкие координаты для карты
- Frontend: `useTaskIncidentsInfinite` (очередь), `useTaskIncidentsGeocodedMap` (карта), кластеры в `EmergencyMarkerCluster` / `OmskMap`

#### Не ломать

- `_save_cache` / `set_geocode_entry` не должны пробрасывать `PermissionError` наружу
- Лимит fresh Nominatim в списках: `geocode_max_fresh`, `asyncio.to_thread`
- **Не патчить через `docker cp` один файл** — только `docker compose build api` или dev-mount

### 2.4 Схема БД

```text
stored_jobs.task_id          PK, String(16)
stored_incidents             FK task_id, UNIQUE (task_id, row_id)
geocode_cache                PK address_key — глобальный кэш Nominatim
```

- Миграций Alembic **нет** — таблицы создаются через `init_db()` при старте API
- Любое изменение колонок — вручную или добавить Alembic; иначе прод упадёт на старых данных

### 2.5 API-контракт frontend

Префикс: `/api/v1/`. Критичные маршруты для UI:

| Маршрут | Экран |
|---------|-------|
| `GET /dashboard` | DashboardScreen |
| `GET /jobs/{id}/incidents` | Operator, Emergency |
| `GET /jobs/{id}/incidents/map-markers` | Emergency, Dashboard (карта) |
| `POST /jobs/{id}/geocode/warmup` | GeocodeWarmupButton |
| `GET /live/recent` | useLiveFeed (poll 3 с) |
| `POST /complaints` | SubmitComplaintScreen |
| `DELETE /jobs/live0000/incidents/{row_id}` | Operator (только citizen-*) |
| `GET /districts/{id}/report.pdf` | DrilldownScreen |
| `GET /archive/jobs` | ArchiveScreen |

### 2.6 Cache tombstones

`data/cache_tombstones.json` — скрывает «фантомные» job-папки, которые OneDrive не даёт удалить (`src/jobs.py`). Tombstone ≠ удаление с диска. Не коммитить в git.

### 2.7 Docker / деплой

- Предпочтительно: `docker compose build api && docker compose up -d api` или dev-mount (`docker-compose.dev.yml`)
- `docker cp` одного файла ломает импорты — не использовать для geocode/db-модулей
- `./data`, `./cache`, `./dataset` — bind mount; на Windows права и блокировки файлов — частая причина багов
- GPU: `ONNX_DEVICE=cuda`, Ollama для LLM-сводок — без Ollama «Сгенерировать сводку» упадёт, но PDF/Excel из report должны работать

---

## 3. Что стоит отрефакторить (приоритет)

### 🔴 Высокий приоритет

#### 3.1 Разбить `src/main.py`

~50 эндпоинтов в одном файле. Предложение:

```
src/
  main.py              — app factory, lifespan, CORS
  routers/
    jobs.py            — /jobs/*
    archive.py         — /archive/*
    incidents.py       — incidents, geocode, delete citizen
    reports.py         — PDF, Excel, departments
    live.py            — /complaints, /live/recent
    dashboard.py       — /dashboard, /districts/*
```

**Риск:** забыть `_is_live_task()` в одном из роутеров → регрессия live.

#### 3.2 Объединить маппинг инцидентов

Дублирование:

- `app/db/repository.py` → `_incident_to_api()`
- `app/task_incidents.py` → `_row_to_incident()`

Оба делают geocode, severity, agency. **Один модуль** `app/incidents/serialize.py` + использование в DB и parquet-пути.

#### 3.3 Единый слой «источник данных задачи»

Сейчас логика «disk vs postgres vs live» размазана по:

- `jobs.get_report` / `get_labeled_df`
- `task_incidents.list_task_incidents`
- `main._require_task_data`, `_get_task_report`, `_load_labeled_for_export`

**Цель:** `TaskDataSource` с методами `get_report()`, `get_incidents()`, `get_labeled_df()` — внутри ветки live / db / parquet.

#### 3.4 `frontend/src/api/client.js`

- ~360 строк, **дубли** методов: `deleteCitizenIncident`, `geocodeCitizenIncident` объявлены дважды (строки ~95 и ~337)
- Deprecated-алиасы: `geocodeCitizenIncident` → `geocodeIncident`
- Разбить: `api/incidents.js`, `api/reports.js`, `api/archive.js`

#### 3.5 Константа `LIVE_TASK_ID` / `CITIZEN_ROW_PREFIX`

Сейчас:

- Backend: `app/live_stream.py`, `app/db/repository.py`, `app/complaint_submit.py`
- Frontend: `constants.js`, `incidentModel.js`

**Один shared-контракт** или хотя бы backend `app/constants.py` + re-export.

---

### 🟡 Средний приоритет

#### 3.6 Крупные React-экраны

| Файл | Проблема |
|------|----------|
| `DashboardScreen.jsx` | analyst + operator + emergency в одном, много state |
| `OperatorScreen.jsx` | список, фильтры, live merge, geocode, delete |
| `EmergencyScreen.jsx` | карта + очередь + live |

Вынести:

- `useMergedIncidents(liveItems, baseItems)` — общая логика Operator/Emergency
- `IncidentListCard` — карточка обращения
- `useLiveIncidents(taskId)` — poll + dedup по `citizenRowId`

#### 3.7 Live feed: poll vs push

`useLiveFeed.js` — polling каждые 3 с. `uid` с timestamp нужен **только для toast**, не для `id` обращения (уже исправлено в `liveEventToIncident`).

Legacy: `app/live_feed.py` (`next_live_event`) — **старый demo** из parquet, не путать с citizen live.

Удалить после проверки: `useLiveDemoFeed.js` (deprecated re-export).

#### 3.8 `app/report.py`

~600+ строк: JSON report, Excel, dashboard builder. Вынести:

- `report/excel_export.py`
- `report/dashboard.py`

`build_full_excel_from_report` / `build_top10_excel_from_report` — общий helper для live и disk.

#### 3.9 Фоновые задачи в памяти

`_district_tasks`, `_department_export_tasks` в `main.py` — теряются при рестарте API. Для prod: Redis/DB или явно документировать как «только для текущей сессии».

#### 3.10 Миграции БД

Добавить Alembic или хотя бы версионирование schema в `app/db/migrations/`. Сейчас `init_db()` только `create_all`.

---

### 🟢 Низкий приоритет / косметика

- `app/live_feed.py` — переименовать в `demo_live_sampler.py` или удалить, если demo не используется
- `schemas.py` — разнести Pydantic-модели по доменам
- `frontend/src/index.css` — 630+ строк emergency/drilldown; CSS modules или Tailwind-only
- `matchDistrict.js` vs `municipalityCoords.js` — два источника координат MO
- Bundle size: `index-*.js` ~1.5 MB — code splitting по экранам (React.lazy)
- Единый naming: `district` vs `municipality` в API и UI

---

## 4. Тесты — что есть и чего нет

### Покрыто (`tests/`)

| Модуль | Файл |
|--------|------|
| IO Excel | `test_io_cabinet.py` |
| Parquet | `test_parquet.py` |
| PDF | `test_pdf.py` |
| Agency mapping | `test_agency_mapping.py`, `test_agency_summary.py` |
| Classify API | `test_classify_api.py` |
| Address, geocode | `test_address.py`, `test_geocode.py` |
| Geocode worker progress | `test_geocode_worker.py` |
| Task incidents | `test_task_incidents.py` |

### Нет тестов (добавить в первую очередь)

- [ ] `app/live_report.py` — сборка report из Postgres
- [ ] `app/complaint_submit.py` — submit flow (mock ONNX)
- [ ] `delete_citizen_incident` — только citizen-*, счётчики job
- [ ] Live-ветки в `main.py` — PDF/Excel для `live0000` (TestClient)
- [ ] `incidentModel.citizenRowId` / merge live+base на frontend (vitest)
- [ ] `src/jobs.py` — tombstones, get_report fallback chain
- [ ] Устаревший `/live/next` — заменён на `/live/recent` (см. `test_classify_api.py`)
- [ ] E2E: submit → live recent → operator list

---

## 5. Хрупкие места (известные грабли)

| Симптом | Причина | Где смотреть |
|---------|---------|--------------|
| Permission denied geocode_cache | OneDrive mount `./data` | `app/geocode.py`, docker volume |
| Не удаляется cache job | OneDrive lock на parquet | `jobs._remove_job_dir`, tombstones |
| «Задача не найдена» на live PDF/Excel | `_require_completed` без live-ветки | `src/main.py` |
| Карта «нет данных» при live | Мало MO с обращениями в report | `live_report.py`, severity filter |
| DetachedInstanceError | ORM вне session | `live_report.py`, `repository.py` |
| API зависает на списке | Nominatim без лимита | `geocode_max_fresh`, `cache_only` |
| Геокод 0% / >100% | worker progress vs DB; Math.round в UI | `geocode_worker._stats_payload`, `GeocodeWarmupButton` |
| Медленный warmup | seq. запросы + retry failed | `NOMINATIM_CONCURRENCY`, skip failed in `fetch_pending` |
| ModuleNotFound geocode_cache_repo | stale Docker image после docker cp | `docker compose build api` |
| На карте только 500 | limit без pagination | `useTaskIncidentsGeocodedMap`, `/map-markers` |
| Дубли обращений в operator | liveItems + baseItems без merge key | `OperatorScreen` pageItems |
| Phantom job в архиве | tombstone + физическая папка | `cache_tombstones.json` |
| LLM сводка не генерится | Ollama down / модель не pulled | docker `ollama`, `.env` |
| 404 district PDF при live | Пустой report (0 MO) | нужны обращения с severity > 0 |

---

## 6. Безопасность и конфигурация

- **Не коммитить:** `.env`, `data/geocode_cache.json`, `data/live_export/`, `data/cache_tombstones.json`, `cache/`, `dataset/`
- CORS: `allow_origins=["*"]` — ок для хакатона, закрыть в prod
- Нет auth на API — любой может submit/delete citizen incidents
- Postgres defaults в compose: `zeroproblems/zeroproblems` — сменить в prod
- `POST /complaints` без rate limit — риск спама Nominatim и БД

---

## 7. Рекомендуемый порядок рефакторинга

1. **Тесты на live0000 + geocode** — страховка перед любыми изменениями
2. **Вынести `_is_live_task` / `TaskDataSource`** — убрать дубли в main.py
3. **Разбить main.py на routers** — без изменения URL
4. **Объединить `_incident_to_api` / `_row_to_incident`**
5. **Frontend: client.js + useMergedIncidents**
6. **Alembic** — если планируется изменение schema
7. **Auth + rate limit** — если выход за пределы демо

---

## 8. Чеклист перед merge / deploy

- [ ] `pytest tests/` — зелёный
- [ ] `npm run build` во frontend
- [ ] Submit обращения на `/submit` → появляется в operator
- [ ] Delete citizen-обращения (с адресом и без)
- [ ] Drilldown: PDF + Excel Top-10 для `live0000`
- [ ] Dashboard: region PDF, Excel, ведомства
- [ ] Excel upload → progress → dashboard (классический путь)
- [ ] Archive: import / delete DB / delete cache
- [ ] Geocode warmup: прогресс ≤100%, карта растёт по мере geocoded
- [ ] Локальный Nominatim (profile nominatim): submit с адресом Омска → координаты в viewbox
- [ ] Перезапуск `docker compose restart api` — Postgres data на месте
- [ ] Проверка на Windows + OneDrive mount (geocode cache write)

---

## 9. Файлы runtime (не в git)

Добавить/держать в `.gitignore`:

```gitignore
data/geocode_cache.json
data/live_export/
data/geocode/
data/cache_tombstones.json
data/zeroproblems.db
cache/
.env
```

---

## 10. Геокодирование и карта (июнь 2026)

Краткая шпаргалка по последним изменениям.

### Запуск локального Nominatim

```powershell
# Первый раз (PBF + импорт, ~30–90 мин):
docker compose up -d nominatim-pbf
docker compose up -d nominatim

# Всё остальное:
docker compose up -d --build
```

В `.env`:

```env
NOMINATIM_URL=http://nominatim:8080
NOMINATIM_MIN_INTERVAL_SEC=0
NOMINATIM_CONCURRENCY=8
GEOCODE_WARMUP_BATCH=80
NOMINATIM_PORT=8088
```

Проверка: `curl "http://localhost:8088/search?q=Омск&format=json&limit=1"`

### Схема `geocode_cache`

```text
geocode_cache
  address_key   PK  — normalized address
  address_line      — исходная строка
  lat, lng          — координаты или NULL
  failed            — true = Nominatim не нашёл; не ретраить в warmup
  updated_at
```

### API warmup

```http
POST /api/v1/jobs/{task_id}/geocode/warmup   # старт
GET  /api/v1/jobs/{task_id}/geocode/warmup   # статус
DELETE /api/v1/jobs/{task_id}/geocode/warmup # остановка
```

Ответ: `progress_pct`, `pending_addresses`, `geocoded_incidents`, `status` (idle|running|done|stopped|error).

### Карта на frontend

- **Экстренный:** очередь — infinite scroll 200/стр.; карта — все geocoded через `/map-markers`
- **Аналитик:** `OmskMap` + MarkerCluster
- Фильтр по дате: `IncidentDateFilter`, params `created_from` / `created_to`

### Типичные цифры (большая задача ~420k обращений)

- ~17k уникальных адресов с улицей
- ~99% rural/obscure адресов могут не найтись в локальном Nominatim — это нормально
- Омские улицы геокодируются после нормализации запроса

---

*Документ можно обновлять по мере рефакторинга. При изменении `live0000`, schema Postgres, формата report.json или geocode API — обновить разделы 2 и 10.*
