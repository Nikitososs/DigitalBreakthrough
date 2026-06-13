import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown } from 'lucide-react'

function DropdownPanel({ open, anchorRef, children }) {
  const [style, setStyle] = useState(null)

  useEffect(() => {
    if (!open || !anchorRef.current) {
      setStyle(null)
      return undefined
    }

    const update = () => {
      const el = anchorRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      setStyle({
        position: 'fixed',
        top: rect.bottom + 4,
        left: rect.left,
        width: rect.width,
        zIndex: 10000,
      })
    }

    update()
    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
    }
  }, [open, anchorRef])

  if (!open || !style) return null
  return createPortal(
    <div style={style} className="searchable-select__portal">
      {children}
    </div>,
    document.body,
  )
}

export default function SearchableSelect({
  value,
  onChange,
  options = [],
  placeholder = '',
  required = false,
  disabled = false,
  className = '',
  inputClassName = '',
  onInputChange,
  /** Только выбор из списка: onChange не вызывается при наборе текста (для фильтров). */
  commitOnPick = false,
  emptyMessage = 'Нет вариантов',
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState(value || '')
  const [highlight, setHighlight] = useState(0)
  const rootRef = useRef(null)
  const anchorRef = useRef(null)
  const listId = useId()

  useEffect(() => {
    if (!open) setQuery(value || '')
  }, [value, open])

  const normalized = (query || '').trim().toLowerCase()
  const filtered = normalized
    ? options.filter((o) => o.toLowerCase().includes(normalized))
    : options

  useEffect(() => {
    setHighlight(0)
  }, [query, open])

  useEffect(() => {
    const onDoc = (e) => {
      const portal = document.querySelector('.searchable-select__portal')
      if (
        rootRef.current?.contains(e.target)
        || portal?.contains(e.target)
      ) {
        return
      }
      setOpen(false)
      setQuery(value || '')
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [value])

  const pick = (option) => {
    onChange(option)
    setQuery(option)
    setOpen(false)
  }

  const clear = () => {
    onChange('')
    setQuery('')
    setOpen(false)
  }

  const handleKeyDown = (e) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      setOpen(true)
      return
    }
    if (e.key === 'Escape') {
      setOpen(false)
      setQuery(value || '')
      return
    }
    if (!open || filtered.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight((h) => (h + 1) % filtered.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight((h) => (h - 1 + filtered.length) % filtered.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      pick(filtered[highlight])
    }
  }

  const fieldCls = inputClassName || 'w-full rounded-lg px-3 py-2 text-sm border outline-none focus:ring-2 focus:ring-red-500/20'
  const fieldStyle = { background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text)' }

  const showClearOption = commitOnPick && Boolean(value)
  const listItems = showClearOption ? [null, ...filtered] : filtered

  const listPanel = open && listItems.length > 0 ? (
    <ul
      id={listId}
      role="listbox"
      className="w-full max-h-48 overflow-y-auto rounded-lg border shadow-lg py-1 text-sm"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
    >
      {listItems.map((option, idx) => {
        if (option === null) {
          return (
            <li
              key="__clear__"
              role="option"
              aria-selected={!value}
              onMouseDown={(e) => e.preventDefault()}
              onClick={clear}
              onMouseEnter={() => setHighlight(idx)}
              className="px-3 py-2 cursor-pointer truncate italic"
              style={{
                background: idx === highlight ? 'var(--bg-sub)' : 'transparent',
                color: 'var(--muted)',
              }}
            >
              {placeholder || 'Сбросить'}
            </li>
          )
        }
        return (
          <li
            key={option}
            role="option"
            aria-selected={option === value}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => pick(option)}
            onMouseEnter={() => setHighlight(idx)}
            className="px-3 py-2 cursor-pointer truncate"
            style={{
              background: idx === highlight ? 'var(--bg-sub)' : 'transparent',
              color: 'var(--text)',
            }}
          >
            {option}
          </li>
        )
      })}
    </ul>
  ) : null

  const emptyPanel = open && listItems.length === 0 ? (
    <div
      className="w-full rounded-lg border px-3 py-2 text-xs"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--muted)' }}
    >
      {normalized ? 'Нет совпадений' : emptyMessage}
    </div>
  ) : null

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <div className="relative" ref={anchorRef}>
        <input
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          value={open ? query : (value || '')}
          required={required}
          disabled={disabled}
          placeholder={placeholder}
          className={`${fieldCls} pr-9`}
          style={fieldStyle}
          onChange={(e) => {
            const next = e.target.value
            setQuery(next)
            if (commitOnPick) {
              if (!next.trim()) onChange('')
            } else {
              onChange(next)
            }
            onInputChange?.(next)
            setOpen(true)
          }}
          onFocus={() => {
            setQuery(value || '')
            setOpen(true)
          }}
          onKeyDown={handleKeyDown}
        />
        <button
          type="button"
          tabIndex={-1}
          disabled={disabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            setOpen((v) => {
              const next = !v
              if (next) setQuery(value || '')
              return next
            })
          }}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md"
          style={{ color: 'var(--muted)' }}
          aria-label="Показать варианты"
        >
          <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
      </div>

      <DropdownPanel open={open} anchorRef={anchorRef}>
        {listPanel || emptyPanel}
      </DropdownPanel>
    </div>
  )
}
