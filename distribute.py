from wallet import send_tokens
from history import log_action

async def distribute_reward(user_address, amount, triggered_by=None):
    tx = await send_tokens(user_address, amount)
    log_action(triggered_by or "system", f"distributed {amount} to {user_address} tx:{tx}")
    return tx
