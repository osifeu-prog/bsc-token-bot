from web3 import Web3
from config import BSC_RPC_URL, TOKEN_CONTRACT_ADDRESS, OWNER_WALLET_ADDRESS, OWNER_WALLET_PRIVATE_KEY, CHAIN_ID
from contracts import token_abi

web3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
if not web3.isConnected():
    print("Warning: Web3 not connected to RPC", BSC_RPC_URL)

contract = web3.eth.contract(address=Web3.to_checksum_address(TOKEN_CONTRACT_ADDRESS), abi=token_abi)

def format_balance(raw):
    try:
        return int(raw)
    except:
        return raw

async def get_balance(address):
    try:
        address = Web3.to_checksum_address(address)
        balance = contract.functions.balanceOf(address).call()
        return format_balance(balance)
    except Exception as e:
        return f"שגיאה: {str(e)}"

async def send_tokens(to, amount):
    try:
        to = Web3.to_checksum_address(to)
        # amount expected as integer smallest unit matching token decimals
        nonce = web3.eth.get_transaction_count(Web3.to_checksum_address(OWNER_WALLET_ADDRESS))
        tx = contract.functions.transfer(to, int(amount)).build_transaction({
            'chainId': CHAIN_ID,
            'gas': 200000,
            'gasPrice': web3.to_wei('5', 'gwei'),
            'nonce': nonce
        })
        signed_tx = web3.eth.account.sign_transaction(tx, OWNER_WALLET_PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return web3.to_hex(tx_hash)
    except Exception as e:
        return f"שגיאה: {str(e)}"
