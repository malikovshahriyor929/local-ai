import { getDb } from './db'

export const settingsService = {
  async getAll() {
    const db = await getDb()
    const rows = await db.all('SELECT key, value FROM settings')
    return rows.reduce((acc, row) => ({ ...acc, [row.key]: row.value }), {})
  },
  async save(values: Record<string, any>) {
    const db = await getDb()
    const stmt = await db.prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)')
    for (const [key, value] of Object.entries(values)) {
      await stmt.run(key, String(value))
    }
    await stmt.finalize()
  },
}
