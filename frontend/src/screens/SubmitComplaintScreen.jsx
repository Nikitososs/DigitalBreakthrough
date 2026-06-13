import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  Loader2,
  MapPin,
  Send,
  AlertCircle,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  FileText,
} from 'lucide-react'
import ThemeToggle from '../components/ThemeToggle'
import ClassificationResultCard from '../components/ClassificationResultCard'
import SearchableSelect from '../components/SearchableSelect'
import { api } from '../api/client'

const EXAMPLES = [
  {
    text: 'Уважаемая администрация! В нашем доме по адресу г. Омск, ул. Ленина, д. 12 уже третий день нет горячей воды. Жильцы с детьми и пожилыми людьми вынуждены греть воду на плите. Просим срочно разобраться с управляющей компанией и восстановить подачу ГВС.',
    group: 'ЖКХ',
    topic: 'Отсутствие горячей воды',
    municipality: 'Омск г.о.',
    settlement: 'Омск',
    street: 'Ленина',
    house: '12',
  },
  {
    text: 'На перекрёстке ул. 10 лет Октября и Красного Пути образовалась глубокая яма диаметром около метра. Автомобили объезжают по встречке, создавая аварийную ситуацию. Прошу отремонтировать дорожное покрытие в кратчайшие сроки.',
    group: 'Дороги',
    topic: 'Ямы на дороге',
    municipality: 'Омск г.о.',
    settlement: 'Омск',
    street: '10 лет Октября',
    house: '',
  },
  {
    text: 'Во дворе дома на ул. 22 Апреля контейнеры переполнены уже неделю, мусор разбросан по территории. Появился неприятный запах, к мусору подходят собаки. УК не вывозит отходы по графику.',
    group: 'ЖКХ',
    topic: 'Вывоз мусора',
    municipality: 'Омск г.о.',
    settlement: 'Омск',
    street: '22 Апреля',
    house: '5',
  },
  {
    text: 'На улице Маяковского между домами 8 и 10 не горит фонарь уже более двух недель. Вечером участок полностью тёмный, жители боятся выходить из дома. Просим заменить лампу или отремонтировать освещение.',
    group: 'ЖКХ',
    topic: 'Уличное освещение',
    municipality: 'Омск г.о.',
    settlement: 'Омск',
    street: 'Маяковского',
    house: '8',
  },
  {
    text: 'После сильного дождя во дворе по ул. Интернациональной затопило подвалы и парковку. Вода стоит вторые сутки, насос не работает. Есть риск затопления жилых помещений, нужна помощь коммунальных служб.',
    group: 'ЖКХ',
    topic: 'Затопление',
    municipality: 'Омск г.о.',
    settlement: 'Омск',
    street: 'Интернациональная',
    house: '3',
  },
]

export default function SubmitComplaintScreen({
  taskId,
  useLiveStream = false,
  onBack,
  onSubmitted,
  standalone = false,
  dark,
  onToggleTheme,
}) {
  const [text, setText] = useState('')
  const [group, setGroup] = useState('')
  const [topic, setTopic] = useState('')
  const [municipality, setMunicipality] = useState('')
  const [settlement, setSettlement] = useState('')
  const [street, setStreet] = useState('')
  const [house, setHouse] = useState('')
  const [activeExample, setActiveExample] = useState(null)
  const [addressOpen, setAddressOpen] = useState(false)
  const [classifying, setClassifying] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState(null)
  const [submitted, setSubmitted] = useState(null)
  const [facets, setFacets] = useState({ groups: [], topics: [], municipalities: [] })

  useEffect(() => {
    api.getReferenceFacets({ severityMin: 0, severityMax: 4 })
      .then((data) => {
        setFacets({
          groups: data.groups || [],
          topics: data.topics || [],
          municipalities: data.municipalities || [],
        })
      })
      .catch(() => {})
  }, [])

  const applyExample = (idx) => {
    const ex = EXAMPLES[idx]
    setText(ex.text)
    setGroup(ex.group)
    setTopic(ex.topic)
    setMunicipality(ex.municipality)
    setSettlement(ex.settlement)
    setStreet(ex.street)
    setHouse(ex.house)
    setActiveExample(idx)
    setPreview(null)
    setError('')
    setAddressOpen(true)
  }

  const handleReset = () => {
    setText('')
    setGroup('')
    setTopic('')
    setMunicipality('')
    setSettlement('')
    setStreet('')
    setHouse('')
    setActiveExample(null)
    setPreview(null)
    setSubmitted(null)
    setError('')
  }

  const handleClassify = async () => {
    if (text.trim().length < 10) {
      setError('Текст обращения — минимум 10 символов')
      return
    }
    setClassifying(true)
    setError('')
    setPreview(null)
    try {
      const res = await api.classify([{ text, group, topic }])
      const hit = res.items?.[0]
      if (!hit) throw new Error('Пустой ответ классификатора')
      setPreview(hit)
    } catch (err) {
      setError(err.message || 'Не удалось оценить обращение. Попробуйте ещё раз.')
    } finally {
      setClassifying(false)
    }
  }

  const handleSubmit = async () => {
    if (!useLiveStream && !taskId) {
      setError('Сервис временно недоступен. Попробуйте позже.')
      return
    }
    if (!municipality.trim()) {
      setError('Укажите муниципалитет')
      setAddressOpen(true)
      return
    }
    if (!preview) {
      await handleClassify()
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const payload = {
        text,
        group,
        topic,
        municipality,
        settlement,
        street,
        house,
      }
      const res = useLiveStream
        ? await api.submitComplaintLive(payload)
        : await api.submitComplaint(taskId, payload)
      setSubmitted(res.incident)
      onSubmitted?.(res.incident)
    } catch (err) {
      setError(err.message || 'Не удалось отправить обращение')
    } finally {
      setSubmitting(false)
    }
  }

  const pageCls = standalone ? 'citizen-submit-page' : 'min-h-screen flex flex-col'
  const canClassify = text.trim().length >= 10

  return (
    <div className={pageCls} style={standalone ? undefined : { background: 'var(--bg)' }}>
      <header className={standalone ? 'citizen-submit-header' : 'px-4 py-3 flex items-center gap-3 border-b sticky top-0 z-10'}
        style={standalone ? undefined : { borderColor: 'var(--border)', background: 'var(--bg-card)' }}
      >
        {!standalone && onBack && (
          <button type="button" onClick={onBack} className="p-2 rounded-xl" style={{ color: 'var(--muted)' }}>
            <ArrowLeft className="w-5 h-5" />
          </button>
        )}
        <div className={standalone ? 'citizen-submit-header__inner' : 'flex-1'}>
          {standalone && (
            <div className="citizen-submit-header__icon" aria-hidden>
              <FileText className="w-5 h-5 text-red-600" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h1 className={standalone ? 'citizen-submit-header__title' : 'text-sm font-bold'} style={standalone ? undefined : { color: 'var(--text)' }}>
              {standalone ? 'Обращение гражданина' : 'Подать обращение'}
            </h1>
            <p className={standalone ? 'citizen-submit-header__subtitle' : 'text-[11px]'} style={standalone ? undefined : { color: 'var(--muted)' }}>
              {standalone
                ? 'Опишите проблему — мы оценим срочность и передадим обращение в работу'
                : (taskId ? `Задача ${taskId}` : 'Нет активной задачи')}
            </p>
          </div>
        </div>
        {onToggleTheme && <ThemeToggle dark={dark} onToggle={onToggleTheme} />}
      </header>

      <main className={standalone ? 'citizen-submit-main' : 'flex-1 p-4 max-w-2xl mx-auto w-full space-y-4 pb-10'}>
        {!submitted && (
        <div className={standalone ? 'citizen-submit-card' : 'rounded-2xl p-5 shadow-sm'}
          style={standalone ? undefined : { background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <div className="citizen-submit-examples">
            <span className="citizen-submit-examples__label">Примеры:</span>
            {EXAMPLES.map((_, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => applyExample(idx)}
                className={`citizen-submit-examples__chip${activeExample === idx ? ' citizen-submit-examples__chip--active' : ''}`}
              >
                Пример {idx + 1}
              </button>
            ))}
          </div>

          <textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value)
              setPreview(null)
              setActiveExample(null)
            }}
            rows={6}
            className="citizen-submit-textarea"
            placeholder="Опишите проблему: что случилось, где, как давно…"
          />

          <div className="citizen-submit-fields">
            <div>
              <label className="citizen-submit-label">Группа</label>
              <SearchableSelect
                value={group}
                onChange={(v) => { setGroup(v); setPreview(null) }}
                options={facets.groups}
                placeholder="ЖКХ"
                inputClassName="citizen-submit-input"
              />
            </div>
            <div>
              <label className="citizen-submit-label">Тема</label>
              <SearchableSelect
                value={topic}
                onChange={(v) => { setTopic(v); setPreview(null) }}
                options={facets.topics}
                placeholder="Отсутствие горячей воды"
                inputClassName="citizen-submit-input"
              />
            </div>
          </div>

          <button
            type="button"
            onClick={() => setAddressOpen((v) => !v)}
            className="citizen-submit-address-toggle"
          >
            <span className="flex items-center gap-2">
              <MapPin className="w-3.5 h-3.5 text-red-600" />
              Адрес и муниципалитет
            </span>
            {addressOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {addressOpen && (
            <div className="citizen-submit-address anim-fade">
              <div>
                <label className="citizen-submit-label">Муниципалитет *</label>
                <SearchableSelect
                  value={municipality}
                  onChange={setMunicipality}
                  options={facets.municipalities}
                  placeholder="Омск г.о."
                  required
                  inputClassName="citizen-submit-input"
                />
              </div>
              <input
                value={settlement}
                onChange={(e) => setSettlement(e.target.value)}
                className="citizen-submit-input"
                placeholder="Населённый пункт"
              />
              <div className="grid grid-cols-3 gap-2">
                <input
                  value={street}
                  onChange={(e) => setStreet(e.target.value)}
                  className="citizen-submit-input col-span-2"
                  placeholder="Улица"
                />
                <input
                  value={house}
                  onChange={(e) => setHouse(e.target.value)}
                  className="citizen-submit-input"
                  placeholder="Дом"
                />
              </div>
            </div>
          )}

          <div className="citizen-submit-actions">
            <span className="citizen-submit-counter">{text.length} симв.</span>
            <div className="citizen-submit-actions__buttons">
              <button type="button" onClick={handleReset} className="citizen-submit-btn citizen-submit-btn--ghost">
                <RotateCcw className="w-4 h-4" />
                Сброс
              </button>
              <button
                type="button"
                onClick={handleClassify}
                disabled={classifying || !canClassify}
                className="citizen-submit-btn citizen-submit-btn--primary"
              >
                {classifying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Классифицировать
              </button>
            </div>
          </div>
        </div>
        )}

        {error && !submitted && (
          <div className="citizen-submit-error">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {submitted && (
          <div className="citizen-submit-success">
            <div className="citizen-submit-success__banner">
              <CheckCircle2 className="w-5 h-5" />
              Обращение принято
            </div>
            <ClassificationResultCard
              severity={submitted.severity}
              label={submitted.label}
              confidence={submitted.confidence}
              category={group || submitted.group || submitted.topic}
            />
            <p className="citizen-submit-success__hint">
              Спасибо! Ваше обращение зарегистрировано и будет рассмотрено ответственными службами.
            </p>
            <button
              type="button"
              onClick={handleReset}
              className="citizen-submit-btn citizen-submit-btn--primary citizen-submit-btn--wide"
            >
              Подать ещё одно обращение
            </button>
          </div>
        )}

        {preview && !submitted && (
          <ClassificationResultCard
            severity={preview.severity}
            label={preview.label}
            confidence={preview.confidence}
            category={group || preview.group || preview.topic}
          >
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || (!useLiveStream && !taskId)}
              className="citizen-submit-btn citizen-submit-btn--primary citizen-submit-btn--wide mt-5"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Отправить обращение
            </button>
            <p className="citizen-submit-submit-hint">
              После отправки обращение будет передано на рассмотрение
            </p>
          </ClassificationResultCard>
        )}
      </main>
    </div>
  )
}
