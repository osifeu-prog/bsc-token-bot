const fs = require('fs');
const file = 'users.json';

function saveUser(userId, wallet) {
  const users = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file)) : {};
  users[userId] = wallet;
  fs.writeFileSync(file, JSON.stringify(users));
}

function getUsers() {
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file)) : {};
}

module.exports = { saveUser, getUsers };
