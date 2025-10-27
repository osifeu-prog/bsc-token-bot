from web3 import Web3
from config import BSC_RPC_URL, TOKEN_CONTRACT_ADDRESS, OWNER_WALLET_ADDRESS, OWNER_WALLET_PRIVATE_KEY
from contracts import token_abi

web3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
contract = web3.eth.contract(address=TOKEN_CONTRACT_ADDRESS, abi=token_abi)

async def get_balance(address):
    try:
        return contract.functions.balanceOf(address).call()
    except Exception as e:
        return f"שגיאה: {str(e)}"

async def send_tokens(to, amount):
    try:
        nonce = web3.eth.get_transaction_count(OWNER_WALLET_ADDRESS)
        tx = contract.functions.transfer(to, amount).build_transaction({
            'chainId': 56,
            'gas': 200000,
            'gasPrice': web3.to_wei('5', 'gwei'),
            'nonce': nonce
        })
        signed_tx = web3.eth.account.sign_transaction(tx, OWNER_WALLET_PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return web3.to_hex(tx_hash)
    except Exception as e:
        return f"שגיאה: {str(e)}"
