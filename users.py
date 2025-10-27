users = {}

def register_user(user_id, wallet_address):
    users[user_id] = {
        "wallet": wallet_address,
        "store": []
    }

def get_user(user_id):
    return users.get(user_id)
