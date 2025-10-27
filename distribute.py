from wallet import send_tokens
from history import log_action

def distribute_reward(telegram_id: int, user_address: str, amount_slh: float):
    tx = send_tokens(user_address, amount_slh)
    log_action(telegram_id, f"distribute {amount_slh} SLH to {user_address}", metadata=str(tx))
    return tx
