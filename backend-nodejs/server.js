// =========================================
// server.js — Point d'entrée
// =========================================
require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');

const authRoutes = require('./routes/auth');
const eleveRoutes = require('./routes/eleves');
const noteRoutes = require('./routes/notes');
const paiementRoutes = require('./routes/paiements');
const communiqueRoutes = require('./routes/communiques');
const { notFoundHandler, errorHandler } = require('./middleware/errorMiddleware');

const app = express();

app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/eleves', eleveRoutes);
app.use('/api', noteRoutes);       // /api/notes, /api/bulletins
app.use('/api', paiementRoutes);   // /api/frais, /api/paiements
app.use('/api', communiqueRoutes); // /api/communiques, /api/messages

app.get('/api/health', (req, res) => {
  res.json({ success: true, message: 'API École La Bonté opérationnelle.' });
});

// 404 + gestion d'erreurs (toujours en dernier)
app.use(notFoundHandler);
app.use(errorHandler);

const { demarrerWebSocket } = require('./utils/websocket');

const PORT = process.env.PORT || 3000;
const httpServer = app.listen(PORT, () => {
  console.log(`✅ Serveur démarré sur http://localhost:${PORT}`);
  console.log(`🔌 WebSocket messagerie disponible sur ws://localhost:${PORT}/ws`);
});

demarrerWebSocket(httpServer);

module.exports = app;
