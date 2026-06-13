from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# --- 1. Загрузка датасета ---

class DatasetUploadResponse(BaseModel):
    """Схема ответа при успешной загрузке датасета"""
    task_id: str = Field(..., description="ID фоновой задачи обработки", example="a1b2c3d4")
    filename: str = Field(..., description="Имя загруженного файла", example="dataset_2023.xlsx")
    message: str = Field(..., description="Статус обработки", example="Датасет успешно загружен и обработан")
    rows_processed: int = Field(..., description="Количество обработанных строк", example=15000)


# --- 2. Дашборд (Главная страница) ---

class DistrictShortInfo(BaseModel):
    """Краткая информация по району (для карты и топа)"""
    district_id: int = Field(..., description="Уникальный идентификатор района", example=1)
    district_name: str = Field(..., description="Название района", example="Центральный АО")
    score: int = Field(..., description="Индекс проблемности (5–100, чем выше — тем больше проблем)", example=87)
    main_problem: str = Field(..., description="Главная проблема", example="ЖКХ")
    analytical_summary: Optional[str] = Field(None, description="Аналитический вывод по МО")
    center_coordinates: Optional[List[float]] = Field(None, description="Координаты центра района [широта, долгота]", example=[54.989347, 73.368221])

class ThemeCount(BaseModel):
    """Счетчик инцидентов по теме"""
    theme: str = Field(..., description="Название темы", example="Дороги")
    count: int = Field(..., description="Количество", example=287)

class CriticalDistrictCard(BaseModel):
    """Карточка критического района"""
    district_id: int = Field(..., description="ID района", example=5)
    district_name: str = Field(..., description="Название района", example="Калачинский район")
    criticality_status: str = Field(..., description="Статус критичности (КРИТИЧНЫЙ, ОЧЕНЬ ВЫСОКИЙ и т.д.)", example="КРИТИЧНЫЙ")
    score: int = Field(..., description="Скор района", example=22)
    top_themes: List[ThemeCount] = Field(..., description="Топ проблем с количеством обращений")
    sample_incident_text: str = Field(..., description="Цитата/пример обращения", example="Мост в аварийном состоянии, проезд опасен")
    analytical_summary: Optional[str] = Field(None, description="Развёрнутый аналитический вывод по критическому МО")
    total_incidents: int = Field(..., description="Всего обращений по району", example=702)

class DashboardResponse(BaseModel):
    """Сводные данные для главной страницы (дашборда)"""
    map_data: List[DistrictShortInfo] = Field(..., description="Данные для карты")
    top_districts: List[DistrictShortInfo] = Field(..., description="Топ-10 районов по скору")
    critical_districts: List[CriticalDistrictCard] = Field(..., description="Карточки критических районов")
    start_date: Optional[datetime] = Field(None, description="Начало периода обращений в датасете")
    end_date: Optional[datetime] = Field(None, description="Конец периода обращений в датасете")
    total_incidents: Optional[int] = Field(None, description="Всего обращений в выборке", example=15000)
    problem_count: Optional[int] = Field(None, description="Проблемных обращений (severity > 0)", example=12000)


# --- 3. Отчёт по району (уже существующий/быстрый) ---

class ThematicGroupStat(BaseModel):
    """Статистика по конкретной тематической группе"""
    group_name: str = Field(..., description="Название тематической группы", example="Транспорт")
    count: int = Field(..., description="Количество обращений (нерешённых для графика)", example=345)
    percentage: float = Field(..., description="Процент от общего числа", example=39.0)
    total_count: Optional[int] = Field(
        None,
        description="Всего проблемных обращений по теме (для таблицы долей)",
        example=400,
    )
    resolved_pct: Optional[float] = Field(
        None,
        description="Доля решённых внутри темы, %",
        example=62.5,
    )


class SeverityStat(BaseModel):
    """Распределение обращений по классу тяжести (0–4)"""
    severity: int = Field(..., description="Класс тяжести", example=2)
    label: str = Field(..., description="Название класса", example="Средняя тяжесть")
    count: int = Field(..., description="Количество обращений", example=45)
    percentage: float = Field(..., description="Процент от общего числа", example=21.4)


class IncidentExample(BaseModel):
    """Пример обращения с классом тяжести"""
    text: str = Field(..., description="Текст обращения")
    severity: int = Field(..., description="Класс тяжести ONNX (1–4)", example=3)
    label: str = Field(..., description="Название класса", example="Высокая")


class DistrictReport(BaseModel):
    """Подробный отчёт по району"""
    district_id: int = Field(..., description="ID района", example=1)
    district_name: str = Field(..., description="Название района", example="Большеуковский район")
    score: int = Field(..., description="Скор/Индекс района", example=25)
    analytical_summary: str = Field(..., description="Аналитическая сводка (текст)", example="Критически низкий уровень транспортной доступности.")
    total_incidents: int = Field(..., description="Всего инцидентов за период", example=879)
    top_category: str = Field(..., description="Топ-категория (больше всего жалоб)", example="Транспорт")
    categories_count: int = Field(..., description="Количество типов проблем", example=4)
    resolved_pct: Optional[float] = Field(
        None,
        description="Доля решённых проблемных обращений (с датой закрытия), %",
        example=42.5,
    )
    resolved_count: Optional[int] = Field(None, description="Число решённых проблемных обращений", example=120)
    problem_count: Optional[int] = Field(None, description="Число проблемных обращений для расчёта доли", example=280)
    start_date: Optional[datetime] = Field(None, description="Начало периода")
    end_date: Optional[datetime] = Field(None, description="Конец периода")
    themes_stat: List[ThematicGroupStat] = Field(..., description="Статистика по категориям (для графиков)")
    severity_stat: List[SeverityStat] = Field(
        default_factory=list,
        description="Распределение обращений по классу тяжести ONNX (0–4)",
    )
    incident_examples: List[IncidentExample] = Field(
        default_factory=list,
        description="Примеры проблемных обращений (severity > 0)",
    )

class DistrictReportResponse(BaseModel):
    """Схема ответа при запросе отчёта по району"""
    data: DistrictReport


class RegionPdfRequest(BaseModel):
    """Сводный PDF по нескольким муниципалитетам (demo / кастомная выборка)"""
    districts: List[DistrictReport] = Field(..., description="Отчёты по МО")
    executive_summary: str = Field("", description="Общая справка по региону")


# --- 4. Создание подробного отчёта по запросу ---

class GenerateReportRequest(BaseModel):
    """Схема запроса на генерацию нового подробного отчёта"""
    district_id: int = Field(..., description="ID района для отчёта", example=1)
    start_date: Optional[datetime] = Field(None, description="Начало периода (опционально)")
    end_date: Optional[datetime] = Field(None, description="Конец периода (опционально)")
    include_raw_data: bool = Field(False, description="Включать ли примеры исходных данных")

class GenerateReportResponse(BaseModel):
    """
    Схема ответа на запрос генерации.
    Так как ML-задачи и генерация отчётов могут быть долгими,
    лучше возвращать ID задачи (Background Task), статус которой фронтенд сможет проверять.
    """
    task_id: str = Field(..., description="ID фоновой задачи генерации отчёта", example="task-12345-abcde")
    status: str = Field(..., description="Текущий статус", example="processing")
    message: str = Field(..., description="Сообщение для пользователя", example="Отчёт генерируется, пожалуйста, подождите.")


# --- 5. Фоновые задачи (пайплайн) ---

class PipelineStep(BaseModel):
    """Шаг обработки датасета"""
    id: str = Field(..., description="Идентификатор шага", example="classify")
    label: str = Field(..., description="Название шага", example="Классификация ONNX")
    status: str = Field(..., description="Статус: pending, running, done, error", example="running")
    detail: str = Field("", description="Детали выполнения")
    progress: float | None = Field(None, description="Подпрогресс шага 0–100", example=42.0)
    duration_sec: float | None = Field(None, description="Длительность шага в секундах", example=12.4)
    started_at: str | None = Field(None, description="Время начала шага (ISO)")
    ended_at: str | None = Field(None, description="Время окончания шага (ISO)")


class JobStatus(BaseModel):
    """Статус фоновой задачи обработки датасета"""
    task_id: str = Field(..., description="ID задачи", example="a1b2c3d4")
    status: str = Field(..., description="queued, running, completed, failed", example="running")
    message: str | None = Field(None, description="Текущее сообщение")
    created_at: str | None = Field(None, description="Время создания (ISO)")
    filename: str | None = Field(None, description="Имя загруженного файла")
    rows_processed: int | None = Field(None, description="Обработано строк")
    stats: dict | None = Field(None, description="Статистика после завершения")
    steps: list[PipelineStep] | None = Field(None, description="Шаги пайплайна")
    progress: float | None = Field(None, description="Общий прогресс пайплайна 0–100", example=35.5)


class PipelineOptions(BaseModel):
    """Параметры запуска пайплайна"""
    skip_summary: bool = Field(False, description="Пропустить LLM-справки")
    batch_size: int = Field(16, description="Размер батча ONNX")
    nrows: int | None = Field(None, description="Ограничить число строк (для теста)")
    model: str | None = Field(None, description="Модель Ollama (по умолчанию gemma4:e2b)")
    llm_fast_mode: bool = Field(
        True,
        description="Короткие ИИ-сводки (параллельно по Top-10/Top-3) + итоговая справка; false — более развёрнутый текст",
    )


class AgencyPreviewItem(BaseModel):
    name: str
    total_count: int
    critical_count: int
    counts: dict[str, int]
    top_topic: Optional[str] = None
    priority: Optional[str] = None
    contact_email: Optional[str] = None


class MunicipalityPreviewItem(BaseModel):
    name: str
    agencies: List[AgencyPreviewItem]
    administration: Optional[str] = None
    admin_contact_email: Optional[str] = None
    admin_contact_phone: Optional[str] = None
    admin_website: Optional[str] = None
    admin_contact_verified: bool = False


class DepartmentReportsPreview(BaseModel):
    municipalities_count: int
    agencies_count: int
    reports_count: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    municipalities: List[MunicipalityPreviewItem]


class DepartmentReportsStatus(BaseModel):
    task_id: str
    status: str
    message: str = ""
    progress: float = 0
    current: int = 0
    total: int = 0
    current_municipality: Optional[str] = None
    current_agency: Optional[str] = None
    phase: Optional[str] = None
    preview: Optional[DepartmentReportsPreview] = None


# --- Live ONNX-классификация ---

class ClassifyAppealInput(BaseModel):
    """Одно обращение для классификации."""
    text: str = Field(..., description="Текст обращения", min_length=3)
    group: str = Field("", description="Группа тем")
    topic: str = Field("", description="Тема")
    municipality: str = Field("", description="Муниципалитет")
    id: Optional[str] = Field(None, description="Внешний ID обращения")
    created_at: Optional[str] = Field(None, description="Дата создания (ISO или как в Excel)")


class ClassifyRequest(BaseModel):
    """Пакет обращений для ONNX (до 64 шт.)."""
    items: List[ClassifyAppealInput] = Field(..., min_length=1, max_length=64)


class ClassifyResultItem(BaseModel):
    id: Optional[str] = None
    severity: int = Field(..., ge=0, le=4)
    label: str
    confidence: float = Field(..., ge=0, le=1)
    is_problem: bool
    text: str
    group: str = ""
    topic: str = ""
    municipality: str = ""
    created_at: Optional[str] = None


class ClassifyResponse(BaseModel):
    items: List[ClassifyResultItem]
    count: int
    latency_ms: float


class LiveEventResponse(BaseModel):
    """Событие live-потока: обращение + ONNX-класс."""
    id: str
    severity: int = Field(..., ge=0, le=4)
    label: str
    confidence: float
    is_problem: bool
    municipality: str = ""
    settlement: Optional[str] = None
    street: Optional[str] = None
    house: Optional[str] = None
    has_address: bool = False
    lat: Optional[float] = None
    lng: Optional[float] = None
    group: str = ""
    topic: str = ""
    text: str
    created_at: Optional[str] = None
    agency: str = ""
    agency_email: Optional[str] = None
    municipality_admin: Optional[str] = None
    municipality_email: Optional[str] = None
    municipality_phone: Optional[str] = None
    task_id: str
    latency_ms: float
    source: str = "citizen"


class SubmitComplaintRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Текст обращения")
    group: str = Field("", description="Группа")
    topic: str = Field("", description="Тема")
    municipality: str = Field(..., min_length=1, description="Муниципалитет")
    settlement: str = ""
    street: str = ""
    house: str = ""


class SubmitComplaintResponse(BaseModel):
    incident: LiveEventResponse
    message: str = "Обращение принято"


class LiveRecentResponse(BaseModel):
    items: List[LiveEventResponse]
    count: int


# --- Оператор: LLM-письмо в ведомство ---

class OperatorIncident(BaseModel):
    text: str = Field(..., description="Текст обращения")
    severity: int = Field(..., description="Класс тяжести 0–4")
    label: str = Field("", description="Название класса тяжести")
    district: str = Field("", description="Муниципалитет")
    category: str = Field("", description="Категория / тема")


class ComposeEmailRequest(BaseModel):
    incidents: List[OperatorIncident] = Field(..., description="Выбранные обращения")
    agency_name: str = Field(..., description="Название ведомства-получателя")
    agency_email: str = Field("", description="Email ведомства")
    bundle_label: Optional[str] = Field(None, description="Категория пакета (группа тем)")
    model: Optional[str] = Field(None, description="Модель Ollama (опционально)")


class ComposeEmailResponse(BaseModel):
    subject: str = Field(..., description="Тема письма")
    body: str = Field(..., description="Тело письма (готовый текст)")
    agency_name: str
    agency_email: str


# --- Обращения задачи (оператор / экстренный) ---

class TaskIncidentItem(BaseModel):
    id: str
    text: str
    severity: int = Field(..., ge=0, le=4)
    label: str = ""
    municipality: str = ""
    settlement: Optional[str] = None
    street: Optional[str] = None
    house: Optional[str] = None
    address: str = ""
    has_address: bool = False
    lat: Optional[float] = None
    lng: Optional[float] = None
    group: str = ""
    topic: str = ""
    agency: str = ""
    agency_email: Optional[str] = None
    municipality_admin: Optional[str] = None
    municipality_email: Optional[str] = None
    municipality_phone: Optional[str] = None
    created_at: Optional[str] = None
    incident_number: Optional[str] = None
    closed_at: Optional[str] = None
    workflow_step: Optional[str] = None
    outcome: Optional[str] = None
    manually_resolved: bool = False
    resolved_at: Optional[str] = None
    resolved_note: Optional[str] = None


class IncidentResolveRequest(BaseModel):
    note: Optional[str] = Field(None, description="Комментарий к закрытию пробела")
    resolved: bool = Field(True, description="True — отметить решённым, False — снять отметку")


class IncidentResolveResponse(BaseModel):
    task_id: str
    row_id: str
    external_id: Optional[str] = None
    manually_resolved: bool
    resolved_at: Optional[str] = None
    resolved_note: Optional[str] = None


class TaskIncidentsResponse(BaseModel):
    items: List[TaskIncidentItem]
    total: int
    offset: int = 0
    limit: int = 300


class TaskMapMarkerItem(BaseModel):
    id: str
    lat: float
    lng: float
    severity: int = Field(..., ge=0, le=4)
    label: str = ""
    municipality: str = ""
    address: str = ""
    text: str = ""
    group: str = ""
    topic: str = ""
    agency: str = ""
    agency_email: Optional[str] = None
    municipality_admin: Optional[str] = None
    municipality_email: Optional[str] = None
    municipality_phone: Optional[str] = None
    created_at: Optional[str] = None


class TaskMapMarkersResponse(BaseModel):
    items: List[TaskMapMarkerItem]
    total: int
    offset: int = 0
    limit: int = 5000


class TaskIncidentFacetsResponse(BaseModel):
    groups: List[str] = []
    topics: List[str] = []
    municipalities: List[str] = []
    agencies: List[str] = []
    with_address: int = 0
    total: int = 0


class IncidentPackageBundle(BaseModel):
    id: str
    group: str = ""
    topics: List[str] = []
    label: str = ""
    items: List[TaskIncidentItem]
    count: int = 0
    severity_counts: dict = Field(default_factory=dict)


class IncidentAgencyPackage(BaseModel):
    agency_name: str
    agency: str = ""
    agency_email: Optional[str] = None
    bundles: List[IncidentPackageBundle] = []
    total: int = 0


class TaskIncidentPackagesResponse(BaseModel):
    packages: List[IncidentAgencyPackage]
    total: int = 0
    offset: int = 0
    limit: int = 100
    loaded: int = 0


class GeocodeWarmupStatusResponse(BaseModel):
    task_id: str
    status: str = Field(..., description="idle | running | done | stopped | error")
    total_addresses: int = 0
    pending_addresses: int = 0
    processed_addresses: int = 0
    geocoded_addresses: int = 0
    failed_addresses: int = 0
    geocoded_incidents: int = 0
    progress_pct: float = 0.0
    message: str = ""
    started_at: str = ""
    updated_at: str = ""


# --- Архив (БД) ---

class ArchiveJobItem(BaseModel):
    task_id: str
    filename: str = ""
    created_at: str = ""
    stored_at: str = ""
    rows_total: int = 0
    problem_count: Optional[int] = None
    municipality_count: Optional[int] = None
    incident_count: int = 0
    in_cache: bool = False
    is_duplicate: bool = False
    duplicate_of_task_id: Optional[str] = None
    is_duplicate_candidate: bool = False


class ArchiveJobsResponse(BaseModel):
    jobs: List[ArchiveJobItem] = []
    duplicates: List[ArchiveJobItem] = []
    importable: List[ArchiveJobItem] = []
    default_task_id: Optional[str] = None
    live_job: Optional[ArchiveJobItem] = None


class ArchiveImportResponse(BaseModel):
    task_id: str
    incident_count: int
    message: str = ""
    is_duplicate: bool = False
    duplicate_of_task_id: Optional[str] = None


class ArchiveCacheDeleteRequest(BaseModel):
    task_ids: List[str] = Field(..., min_length=1)


class ArchiveCacheDeleteResponse(BaseModel):
    deleted: List[str] = []
    missing: List[str] = []
    count: int = 0


# --- Авторизация ---

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class UserPublic(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)
    role: str = Field(..., description="admin | analyst | operator")


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
    is_active: Optional[bool] = None


# --- Прогноз обращений ---

class ForecastPoint(BaseModel):
    period: str = Field(..., description="Начало недели (ISO) или период прогноза")
    actual: Optional[int] = Field(None, description="Фактическое число обращений")
    predicted: Optional[float] = Field(None, description="Прогнозное число обращений")
    predicted_low: Optional[float] = Field(None, description="Нижняя граница прогноза")
    predicted_high: Optional[float] = Field(None, description="Верхняя граница прогноза")
    is_forecast: bool = Field(..., description="Точка прогноза (не история)")


class ForecastSeries(BaseModel):
    label: str = Field(..., description="Название серии (регион, МО, тема)")
    points: List[ForecastPoint] = Field(default_factory=list)
    trend_pct: float = Field(0.0, description="Процент изменения тренда")
    risk_level: str = Field("стабильный", description="Уровень риска")
    confidence: Optional[str] = Field(None, description="normal | low")
    history_total: int = Field(0, description="Сумма фактических обращений за историю")
    forecast_total: float = Field(0.0, description="Сумма прогноза на горизонт")
    last_week_actual: int = Field(0, description="Обращений за последнюю неделю")
    forecast_next_week: Optional[float] = Field(None, description="Прогноз на следующую неделю")


class ForecastVolumeItem(BaseModel):
    label: str
    value: int
    share_pct: float


class ForecastMonthlyPoint(BaseModel):
    period: str
    count: int


class ForecastSeverityItem(BaseModel):
    label: str
    severity: int
    count: int
    share_pct: float


class ForecastRiskBucket(BaseModel):
    label: str
    count: int


class ForecastHeatmap(BaseModel):
    municipalities: List[str] = Field(default_factory=list)
    weeks: List[str] = Field(default_factory=list)
    values: List[List[int]] = Field(default_factory=list)


class ForecastMapDistrict(BaseModel):
    id: str
    name: str
    score: int = Field(..., description="Индекс прогнозной нагрузки для карты (выше = хуже)")
    trend_pct: float = 0.0
    risk_level: str = "стабильный"
    forecast_next_week: Optional[float] = None


class ForecastKpi(BaseModel):
    avg_weekly_12w: float = 0.0
    forecast_total: float = 0.0
    forecast_avg_weekly: float = 0.0
    peak_week_count: int = 0
    peak_week_date: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    municipalities: int = 0
    topics: int = 0
    rising_municipalities: int = 0
    rising_topics: int = 0
    declining_municipalities: int = 0
    declining_topics: int = 0
    history_weeks: int = 0


class ForecastDataQuality(BaseModel):
    address_pct: float = 0.0
    geocode_pct: float = 0.0
    agencies: int = 0
    closed_at_pct: float = 0.0
    jobs_count: int = 0
    last_upload: Optional[str] = None


class ForecastProcessingAgency(BaseModel):
    label: str
    median_days: float
    count: int


class ForecastWeeklyFlowPoint(BaseModel):
    period: str
    created: int
    closed: int


class ForecastProcessing(BaseModel):
    available: bool = False
    median_days: Optional[float] = None
    p90_days: Optional[float] = None
    closed_count: int = 0
    open_count: int = 0
    closed_share_pct: float = 0.0
    weekly_flow: List[ForecastWeeklyFlowPoint] = Field(default_factory=list)
    slowest_agencies: List[ForecastProcessingAgency] = Field(default_factory=list)


class ForecastResponse(BaseModel):
    source: str = Field("database", description="Источник данных (архив БД)")
    incident_count: int = Field(..., description="Число обращений в выборке прогноза")
    jobs_count: int = Field(..., description="Число файловых загрузок в архиве (как «В базе», без live и дубликатов)")
    horizon_weeks: int = Field(..., description="Горизонт прогноза в неделях (2, 4 или 8)")
    history_weeks: int = Field(..., description="Число недель истории для тренда")
    region_series: ForecastSeries
    region_chart: ForecastSeries
    critical_chart: ForecastSeries = Field(
        default_factory=lambda: ForecastSeries(label="Критичные (3–4)", points=[]),
    )
    monthly_series: List[ForecastMonthlyPoint] = Field(default_factory=list)
    kpis: ForecastKpi
    data_quality: ForecastDataQuality = Field(default_factory=ForecastDataQuality)
    processing: ForecastProcessing = Field(default_factory=ForecastProcessing)
    top_municipalities: List[ForecastVolumeItem] = Field(default_factory=list)
    top_topics: List[ForecastVolumeItem] = Field(default_factory=list)
    top_groups: List[ForecastVolumeItem] = Field(default_factory=list)
    top_agencies: List[ForecastVolumeItem] = Field(default_factory=list)
    severity_breakdown: List[ForecastSeverityItem] = Field(default_factory=list)
    risk_distribution: List[ForecastRiskBucket] = Field(default_factory=list)
    heatmap: ForecastHeatmap = Field(default_factory=ForecastHeatmap)
    map_districts: List[ForecastMapDistrict] = Field(default_factory=list)
    rising_municipalities: List[ForecastSeries] = Field(default_factory=list)
    rising_topics: List[ForecastSeries] = Field(default_factory=list)
    declining_municipalities: List[ForecastSeries] = Field(default_factory=list)
    declining_topics: List[ForecastSeries] = Field(default_factory=list)
    summary_text: str = Field(..., description="Текстовая сводка прогноза")
    generated_at: datetime


class ForecastAiSummaryResponse(BaseModel):
    summary: str = Field(..., description="AI-сводка по всем графикам и трендам прогноза")
    horizon_weeks: int
    model: str = Field(..., description="Модель Ollama")
    from_cache: bool = Field(False, description="Ответ из кэша (без повторного вызова LLM)")
