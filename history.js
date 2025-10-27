const fs = require('fs');
const file = 'history.json';

function logDistribution(to, amount, txHash) {
  const history = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file)) : [];
  history.push({ to, amount, txHash, date: new Date().toISOString() });
  fs.writeFileSync(file, JSON.stringify(history));
}

module.exports = { logDistribution };
