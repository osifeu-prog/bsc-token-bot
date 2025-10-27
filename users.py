# מאגר זיכרון פשוט בזמן ריצה. לשמירה פרקטית, החלף ב‑DB
users = {}

def register_user(user_id, wallet_address=None):
    if user_id not in users:
        users[user_id] = {
            "wallet": wallet_address,
            "store": []
        }
    else:
        if wallet_address:
            users[user_id]["wallet"] = wallet_address
    return users[user_id]

def get_user(user_id):
    return users.get(user_id)

def set_wallet(user_id, wallet_address):
    register_user(user_id, wallet_address)
    users[user_id]["wallet"] = wallet_address
    return users[user_id]
