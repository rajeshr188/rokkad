from psycopg3.extras import CompositeCaster


class MoneyValueAdapter(CompositeCaster):
    def parse(self, obj):
        return {"currency": obj[0], "amount": obj[1]}

    def compose(self, obj):
        return f"({obj['currency']}, {obj['amount']})"
