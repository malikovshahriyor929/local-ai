import sqlite3 from 'sqlite3'
import { open, Database } from 'sqlite'
import { config } from '../config'

let db: Database<sqlite3.Database, sqlite3.Statement> | null = null

export async function getDb() {
  if (db) return db
  db = await open({
    filename: config.databasePath,
    driver: sqlite3.Database,
  })
  await db.exec(`CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
  )`)
  await db.exec(`CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT,
    content TEXT,
    createdAt TEXT
  )`)
  return db
}
