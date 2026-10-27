/**
 * Viral-X Production Server Entrypoint
 */

const app = require('./app');

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`=======================================================`);
  console.log(`  VIRAL-X Production AI Sales Agent Server Online    `);
  console.log(`  URL: http://localhost:${PORT}                       `);
  console.log(`  API Health: http://localhost:${PORT}/api/health     `);
  console.log(`=======================================================`);
});
