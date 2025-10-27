from users import register_user, get_user

def add_product(user_id, product):
    register_user(user_id)
    get_user(user_id)["store"].append(product)

def get_store(user_id):
    u = get_user(user_id)
    if not u:
        return []
    return u.get("store", [])
