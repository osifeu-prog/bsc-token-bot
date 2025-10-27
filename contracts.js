const fs = require('fs');
const file = 'contracts.json';

function saveContract(userId, contract) {
  const contracts = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file)) : {};
  contracts[userId] = contract;
  fs.writeFileSync(file, JSON.stringify(contracts));
}

module.exports = { saveContract };
