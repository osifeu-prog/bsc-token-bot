from wallet import send_tokens

async def distribute_reward(user_address, amount):
    return await send_tokens(user_address, amount)
