import payment
import database as db


class OrderService:
    def create_order(self):
        payment.calculate_price()
        db.save_order()
        self.validate()

    def validate(self):
        return True
