stores = {}

def add_product(user_id, product):
    if user_id not in stores:
        stores[user_id] = []
    stores[user_id].append(product)

def get_store(user_id):
    return stores.get(user_id, [])
