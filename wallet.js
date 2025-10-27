const Web3 = require('web3');
const config = require('./config');
const web3 = new Web3(config.rpcUrl);
const { OWNER_WALLET_PRIVATE_KEY } = process.env;

const account = web3.eth.accounts.privateKeyToAccount(OWNER_WALLET_PRIVATE_KEY);
web3.eth.accounts.wallet.add(account);
web3.eth.defaultAccount = account.address;

module.exports = { web3, account };
