from peewee import *
import os

db = PostgresqlDatabase(
        database="bd_twa_projet",
        user="postgres",
        password="AtOm78180",
        host="host.docker.internal",
        port=5432
        )


class Product(Model):
    id = IntegerField(primary_key=True)
    name = CharField()
    description = CharField()
    price = FloatField()
    in_stock = BooleanField()
    weight = IntegerField()
    image = CharField()

    class Meta:
        database = db


class OrderItem(Model):
    id = AutoField(primary_key=True)
    product = ForeignKeyField(Product, backref='order_items')
    quantity = IntegerField()

    class Meta:
        database = db


class Transaction(Model):
    id = AutoField(primary_key=True)
    credit_card_id = ForeignKeyField(Product, backref='transactions', null=True)
    success = BooleanField()
    amount_charged = FloatField()

    class Meta:
        database = db

class CreditCard(Model):
    credit_card_id=AutoField(primary_key=True)
    credit_card_owner= CharField()
    credit_card_number = CharField()
    credit_card_expiration_year = IntegerField()
    credit_card_expiration_month = IntegerField()
    credit_card_ccv = IntegerField()

    class Meta:
        database = db

class ShippingInfo(Model):
    shipping_id=AutoField(primary_key=True)
    shipping_information_country = CharField()
    shipping_information_address = CharField()
    shipping_information_postal_code = CharField()
    shipping_information_city = CharField()
    shipping_information_province = CharField()

    class Meta:
        database = db

class Order(Model):
    id = AutoField(primary_key=True)
    total_price = FloatField()
    shipping_price = FloatField()
    email = CharField(null=True)
    paid = BooleanField()
    orderItem= ForeignKeyField(OrderItem, backref='orderItem', null=True)
    transaction_id = ForeignKeyField(Transaction, backref='orders', null=True)
    credit_card_id = ForeignKeyField(CreditCard, backref='credit_card', null=True)
    shipping_id = ForeignKeyField(ShippingInfo, backref='shipping_info', null=True)

    class Meta:
        database = db

