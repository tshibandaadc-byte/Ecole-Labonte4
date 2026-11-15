// =========================================
// config/db.js — Connexion PostgreSQL (pool)
// =========================================
const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 5432,
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  database: process.env.DB_NAME || 'ecole_la_bonte',
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
});

pool.on('error', (err) => {
  console.error('Erreur inattendue sur le pool PostgreSQL', err);
  process.exit(-1);
});

module.exports = pool;
