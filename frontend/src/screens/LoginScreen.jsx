import { useState } from 'react'
import { Zap, LogIn, AlertCircle, Eye, EyeOff } from 'lucide-react'
import ThemeToggle from '../components/ThemeToggle'
import { api } from '../api/client'
import { setAuth } from '../auth/storage'

export default function LoginScreen({ onLoggedIn, dark, onToggleTheme }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [shake, setShake] = useState(false)
  const [focusedField, setFocusedField] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    setLoading(true)
    setError('')
    try {
      const res = await api.login(username.trim(), password)
      setAuth(res.access_token, res.user)
      onLoggedIn(res.user)
    } catch (err) {
      setError(err.message || 'Ошибка входа')
      setShake(true)
      setTimeout(() => setShake(false), 500)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen flex flex-col relative overflow-hidden"
      style={{ background: 'var(--bg)' }}
    >
      {/* Фоновые декоративные пятна */}
      <div aria-hidden style={{
        position: 'absolute', top: '-80px', right: '-60px',
        width: '380px', height: '380px', borderRadius: '50%',
        background: 'radial-gradient(circle, #dc26261f 0%, #dc262608 45%, transparent 68%)',
        pointerEvents: 'none',
      }} />
      <div aria-hidden style={{
        position: 'absolute', bottom: '-80px', left: '-40px',
        width: '340px', height: '340px', borderRadius: '50%',
        background: 'radial-gradient(circle, #dc26261a 0%, #dc262606 45%, transparent 68%)',
        pointerEvents: 'none',
      }} />
      <div aria-hidden style={{
        position: 'absolute', top: '38%', left: '-100px',
        width: '300px', height: '300px', borderRadius: '50%',
        background: 'radial-gradient(circle, #dc262614 0%, transparent 65%)',
        pointerEvents: 'none',
      }} />
      <div aria-hidden style={{
        position: 'absolute', top: '20%', right: '8%',
        width: '200px', height: '200px', borderRadius: '50%',
        background: 'radial-gradient(circle, #dc262610 0%, transparent 65%)',
        pointerEvents: 'none',
      }} />
      <div aria-hidden style={{
        position: 'absolute', bottom: '20%', right: '-60px',
        width: '260px', height: '260px', borderRadius: '50%',
        background: 'radial-gradient(circle, #dc262616 0%, transparent 65%)',
        pointerEvents: 'none',
      }} />

      <div className="flex justify-end p-4 relative z-10">
        <ThemeToggle dark={dark} onToggle={onToggleTheme} />
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-4 pb-16 anim-fade relative z-10">

        {/* Логотип */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-20 h-20 mb-5 relative">
            <span aria-hidden style={{
              position: 'absolute', inset: '-6px', borderRadius: '28px',
              border: '2px solid #dc262630',
              animation: 'loginRingPulse 2.4s ease-out infinite',
            }} />
            <span style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '80px', height: '80px', borderRadius: '24px',
              background: 'linear-gradient(145deg, #ef4444 0%, #b91c1c 100%)',
              boxShadow: '0 16px 40px -12px #dc2626aa, inset 0 1px 0 rgb(255 255 255 / 0.18)',
            }}>
              <Zap className="w-9 h-9 text-white" />
            </span>
          </div>

          <h1 className="text-3xl font-bold tracking-tight mb-2" style={{ color: 'var(--text)' }}>
            ZeroProblems
          </h1>

          <div className="flex items-center justify-center gap-2 mt-1">
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: '5px',
              fontSize: '11px', fontWeight: 700, padding: '3px 10px',
              borderRadius: '999px',
              background: 'color-mix(in srgb, #16a34a 14%, var(--bg-card))',
              color: '#15803d',
              border: '1px solid color-mix(in srgb, #16a34a 30%, var(--border))',
            }}>
              <span style={{
                width: '6px', height: '6px', borderRadius: '50%',
                background: '#16a34a', display: 'inline-block',
                animation: 'loginRingPulse 1.8s ease-out infinite',
              }} />
              Система работает
            </span>
          </div>

          <p className="text-sm mt-2" style={{ color: 'var(--muted)' }}>
            Вход для сотрудников
          </p>
        </div>

        {/* Карточка формы */}
        <form
          onSubmit={handleSubmit}
          className="w-full max-w-sm"
          style={{
            background: 'var(--bg-card)',
            border: '1px solid color-mix(in srgb, #dc2626 20%, var(--border))',
            borderRadius: '28px',
            overflow: 'hidden',
            boxShadow: '0 20px 60px -20px rgb(0 0 0 / 0.12), 0 0 0 1px color-mix(in srgb, #dc2626 8%, var(--border)), 0 -4px 24px -8px #dc262630',
            animation: shake ? 'loginShake 0.45s ease' : 'none',
          }}
        >

          <div style={{ padding: '28px' }}>
            <label
              className="block text-xs font-bold mb-2 uppercase"
              style={{ color: 'var(--muted)', letterSpacing: '0.1em' }}
            >
              Логин
            </label>
            <input
              type="text"
              autoComplete="username"
              placeholder="Введите логин"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onFocus={() => setFocusedField('username')}
              onBlur={() => setFocusedField(null)}
              className="w-full text-sm mb-5 outline-none"
              style={{
                borderRadius: '14px',
                padding: '12px 14px',
                background: 'var(--bg-sub)',
                border: focusedField === 'username'
                  ? '1.5px solid color-mix(in srgb, #dc2626 50%, var(--border))'
                  : '1.5px solid var(--border)',
                color: 'var(--text)',
                boxShadow: focusedField === 'username' ? '0 0 0 3px #dc262614' : 'none',
                transition: 'border-color 0.15s, box-shadow 0.15s',
              }}
            />

            <label
              className="block text-xs font-bold mb-2 uppercase"
              style={{ color: 'var(--muted)', letterSpacing: '0.1em' }}
            >
              Пароль
            </label>
            <div className="relative mb-5">
              <input
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="Введите пароль"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={() => setFocusedField('password')}
                onBlur={() => setFocusedField(null)}
                className="w-full text-sm outline-none"
                style={{
                  borderRadius: '14px',
                  padding: '12px 44px 12px 14px',
                  background: 'var(--bg-sub)',
                  border: focusedField === 'password'
                    ? '1.5px solid color-mix(in srgb, #dc2626 50%, var(--border))'
                    : '1.5px solid var(--border)',
                  color: 'var(--text)',
                  boxShadow: focusedField === 'password' ? '0 0 0 3px #dc262614' : 'none',
                  transition: 'border-color 0.15s, box-shadow 0.15s',
                  width: '100%',
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(v => !v)}
                tabIndex={-1}
                style={{
                  position: 'absolute', right: '12px', top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--muted)', padding: '2px',
                  display: 'flex', alignItems: 'center',
                  transition: 'color 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.color = 'var(--text-2)'}
                onMouseLeave={e => e.currentTarget.style.color = 'var(--muted)'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            {error && (
              <div
                className="flex items-start gap-2 text-sm mb-5"
                style={{
                  padding: '10px 14px', borderRadius: '12px',
                  background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c',
                }}
              >
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !username.trim() || !password}
              className="w-full flex items-center justify-center gap-2 text-sm font-bold text-white"
              style={{
                borderRadius: '16px',
                padding: '13px 20px',
                background: 'linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)',
                boxShadow: loading || !username.trim() || !password
                  ? 'none'
                  : '0 8px 24px -8px #dc2626aa, inset 0 1px 0 rgb(255 255 255 / 0.15)',
                opacity: loading || !username.trim() || !password ? 0.55 : 1,
                transition: 'opacity 0.15s, box-shadow 0.15s, transform 0.1s',
                cursor: loading || !username.trim() || !password ? 'not-allowed' : 'pointer',
              }}
              onMouseEnter={e => {
                if (!loading && username.trim() && password)
                  e.currentTarget.style.transform = 'translateY(-1px)'
              }}
              onMouseLeave={e => { e.currentTarget.style.transform = '' }}
            >
              <LogIn className="w-4 h-4" />
              {loading ? 'Вход…' : 'Войти'}
            </button>
          </div>
        </form>
      </div>

      <style>{`
        @keyframes loginRingPulse {
          0%   { transform: scale(0.9); opacity: 0.8; }
          100% { transform: scale(1.4); opacity: 0; }
        }
        @keyframes loginShake {
          0%, 100% { transform: translateX(0); }
          15%       { transform: translateX(-7px); }
          30%       { transform: translateX(6px); }
          45%       { transform: translateX(-5px); }
          60%       { transform: translateX(4px); }
          75%       { transform: translateX(-3px); }
          90%       { transform: translateX(2px); }
        }
      `}</style>
    </div>
  )
}
