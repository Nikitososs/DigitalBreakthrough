import { useCallback, useEffect, useState } from 'react'

import { ArrowLeft, Loader2, Plus, Shield, UserX } from 'lucide-react'

import ThemeToggle from '../components/ThemeToggle'

import { api } from '../api/client'

import { normalizeUserRole, USER_ROLES } from '../auth/roles'



export default function AdminScreen({ onBack, dark, onToggleTheme }) {

  const [users, setUsers] = useState([])

  const [loading, setLoading] = useState(true)

  const [error, setError] = useState('')

  const [creating, setCreating] = useState(false)

  const [form, setForm] = useState({ username: '', password: '', role: 'analyst' })



  const loadUsers = useCallback(async () => {

    setLoading(true)

    setError('')

    try {

      setUsers(await api.listUsers())

    } catch (err) {

      setError(err.message || 'Не удалось загрузить пользователей')

    } finally {

      setLoading(false)

    }

  }, [])



  useEffect(() => {

    loadUsers()

  }, [loadUsers])



  const handleCreate = async (e) => {

    e.preventDefault()

    if (!form.username.trim() || form.password.length < 6) return

    setCreating(true)

    setError('')

    try {

      await api.createUser(form)

      setForm({ username: '', password: '', role: 'analyst' })

      await loadUsers()

    } catch (err) {

      setError(err.message || 'Ошибка создания')

    } finally {

      setCreating(false)

    }

  }



  const handleRoleChange = async (userId, role) => {

    try {

      await api.updateUser(userId, { role })

      await loadUsers()

    } catch (err) {

      setError(err.message || 'Ошибка обновления')

    }

  }



  const handleDeactivate = async (userId) => {

    if (!window.confirm('Отключить пользователя?')) return

    try {

      await api.deactivateUser(userId)

      await loadUsers()

    } catch (err) {

      setError(err.message || 'Ошибка отключения')

    }

  }



  return (

    <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg)', color: 'var(--text)' }}>

      <header

        className="sticky top-0 z-50 px-4 py-3 flex items-center gap-3"

        style={{ background: 'var(--head-bg)', borderBottom: '1px solid var(--border)' }}

      >

        <button type="button" onClick={onBack} className="p-2 rounded-lg hover:opacity-80" title="Назад">

          <ArrowLeft className="w-5 h-5" />

        </button>

        <div className="flex items-center gap-2">

          <Shield className="w-5 h-5 text-red-600" />

          <h1 className="font-bold text-lg">Управление пользователями</h1>

        </div>

        <div className="ml-auto">

          <ThemeToggle dark={dark} onToggle={onToggleTheme} />

        </div>

      </header>



      <main className="flex-1 max-w-3xl w-full mx-auto p-4 space-y-6">

        <form

          onSubmit={handleCreate}

          className="rounded-2xl p-5 space-y-3"

          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}

        >

          <h2 className="font-semibold text-sm flex items-center gap-2">

            <Plus className="w-4 h-4" />

            Новый пользователь

          </h2>

          <div className="grid sm:grid-cols-3 gap-3">

            <input

              placeholder="Логин"

              value={form.username}

              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}

              className="rounded-xl px-3 py-2 text-sm outline-none"

              style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}

            />

            <input

              type="password"

              placeholder="Пароль (мин. 6)"

              value={form.password}

              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}

              className="rounded-xl px-3 py-2 text-sm outline-none"

              style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}

            />

            <select

              value={form.role}

              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}

              className="rounded-xl px-3 py-2 text-sm outline-none"

              style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}

            >

              {USER_ROLES.map((r) => (

                <option key={r.value} value={r.value} title={r.hint}>{r.label}</option>

              ))}

            </select>

          </div>

          <button

            type="submit"

            disabled={creating}

            className="text-sm font-semibold px-4 py-2 rounded-xl text-white"

            style={{ background: '#dc2626' }}

          >

            {creating ? 'Создание…' : 'Создать'}

          </button>

        </form>



        {error && <p className="text-sm text-red-600">{error}</p>}



        {loading ? (

          <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--muted)' }}>

            <Loader2 className="w-4 h-4 animate-spin" />

            Загрузка…

          </div>

        ) : (

          <div className="rounded-2xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>

            <table className="w-full text-sm">

              <thead style={{ background: 'var(--bg-sub)' }}>

                <tr>

                  <th className="text-left px-4 py-2 font-medium">Логин</th>

                  <th className="text-left px-4 py-2 font-medium">Роль</th>

                  <th className="text-left px-4 py-2 font-medium">Статус</th>

                  <th className="px-4 py-2" />

                </tr>

              </thead>

              <tbody>

                {users.map((u) => (

                  <tr key={u.id} style={{ borderTop: '1px solid var(--border)' }}>

                    <td className="px-4 py-3">{u.username}</td>

                    <td className="px-4 py-3">

                      <select

                        value={normalizeUserRole(u.role)}

                        disabled={!u.is_active}

                        onChange={(e) => handleRoleChange(u.id, e.target.value)}

                        className="rounded-lg px-2 py-1 text-xs outline-none"

                        style={{ background: 'var(--bg-sub)', border: '1px solid var(--border)' }}

                      >

                        {USER_ROLES.map((r) => (

                          <option key={r.value} value={r.value}>{r.label}</option>

                        ))}

                      </select>

                    </td>

                    <td className="px-4 py-3" style={{ color: u.is_active ? 'var(--text)' : 'var(--muted)' }}>

                      {u.is_active ? 'Активен' : 'Отключён'}

                    </td>

                    <td className="px-4 py-3 text-right">

                      {u.is_active && (

                        <button

                          type="button"

                          onClick={() => handleDeactivate(u.id)}

                          className="inline-flex items-center gap-1 text-xs text-red-600 hover:underline"

                        >

                          <UserX className="w-3.5 h-3.5" />

                          Отключить

                        </button>

                      )}

                    </td>

                  </tr>

                ))}

              </tbody>

            </table>

          </div>

        )}

      </main>

    </div>

  )

}


