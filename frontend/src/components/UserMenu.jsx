import { useEffect, useRef, useState } from 'react'
import { ChevronDown, LogOut, Settings, User } from 'lucide-react'
import { clearAuth } from '../auth/storage'
import { roleLabel } from '../auth/roles'

export default function UserMenu({ user, onLogout, onOpenAdmin }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  if (!user) return null

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-xl transition-colors hover:opacity-90"
        style={{
          background: 'var(--bg-sub)',
          border: '1px solid var(--border)',
          color: 'var(--text-2)',
        }}
      >
        <User className="w-3.5 h-3.5 flex-shrink-0" />
        <span className="max-w-[6rem] truncate">{user.username}</span>
        <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} style={{ color: 'var(--muted)' }} />
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-1.5 rounded-xl shadow-xl overflow-hidden min-w-[180px] z-50"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
            <p className="text-xs font-bold leading-snug" style={{ color: 'var(--text)' }}>{user.username}</p>
            <p className="text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>{roleLabel(user.role)}</p>
          </div>

          {user.role === 'admin' && (
            <button
              type="button"
              onClick={() => { setOpen(false); onOpenAdmin?.() }}
              className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium transition-colors hover:opacity-80"
              style={{ color: 'var(--text)', background: 'transparent' }}
            >
              <Settings className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--muted)' }} />
              Управление
            </button>
          )}

          <button
            type="button"
            onClick={() => { setOpen(false); clearAuth(); onLogout() }}
            className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium transition-colors hover:opacity-80"
            style={{ color: '#dc2626', background: 'transparent' }}
          >
            <LogOut className="w-3.5 h-3.5 flex-shrink-0" />
            Выйти
          </button>
        </div>
      )}
    </div>
  )
}
