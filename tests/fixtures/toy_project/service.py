from payment import calculate_price
from database import save_order


def create_order():
    price = calculate_price(2, 10000)
    save_order(price)
    return price
