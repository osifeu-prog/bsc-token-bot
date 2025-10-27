const { web3, account } = require('./wallet');
const tokenABI = [ // חלק מה-ABI של ERC-20
  { "constant": false, "inputs": [{ "name": "_to", "type": "address" }, { "name": "_value", "type": "uint256" }], "name": "transfer", "outputs": [{ "name": "", "type": "bool" }], "type": "function" }
];
const tokenAddress = process.env.TOKEN_CONTRACT_ADDRESS;
const tokenContract = new web3.eth.Contract(tokenABI, tokenAddress);

async function sendToken(toAddress, amount) {
  const tx = tokenContract.methods.transfer(toAddress, amount);
  const gas = await tx.estimateGas({ from: account.address });
  const data = tx.encodeABI();

  const txData = {
    from: account.address,
    to: tokenAddress,
    data,
    gas
  };

  const receipt = await web3.eth.sendTransaction(txData);
  return receipt;
}

module.exports = { sendToken };
