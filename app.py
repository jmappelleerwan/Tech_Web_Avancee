import json
import datetime

from flask import Flask, jsonify, request, abort, redirect, url_for, send_from_directory
from peewee import *
from models import OrderItem, Product, Transaction, CreditCard, Order, ShippingInfo, db
from flask_cors import CORS

import requests
import redis

REDIS_URL = "redis://host.docker.internal"
r = redis.from_url(REDIS_URL)

# Testez la connexion
try:
    r.ping()
    print('Connecté à Redis!')
except redis.ConnectionError:
    print('Erreur de connexion à Redis!')


def init_db():
    
    db.connect()
    db.create_tables([Product, OrderItem, CreditCard, ShippingInfo, Order, Transaction], safe=True)
    db.close()




init_db()


app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return send_from_directory('.', 'FE_Post.html')

def clean_data(data):
    try:
        cleaned_data = data.replace('\x00', '')
        return cleaned_data
    except UnicodeDecodeError as e:
        print(f"Erreur de décodage Unicode : {e}")
        return ""
    except Exception as e:
        print(f"Une erreur est survenue : {e}")
        return ""




url = 'http://dimprojetu.uqac.ca/~jgnault/shops/products/'
response = requests.get(url)

if response.status_code == 200:
    liste_produit = response.json()
    
    
    for produit in liste_produit['products']:
        deja_present = Product.select().where(Product.id == produit['id']).first()
    
        if deja_present is None:
            Product.create(
                id=produit['id'],
                name=clean_data(produit['name']),
                description=clean_data(produit['description']),
                price=produit['price'],
                in_stock=produit['in_stock'],
                weight=produit['weight'],
                image=produit['image']
            )
            print("produit", produit['name'], "créé")
        else:
            
            print("Le produit", produit['name'], "existe déjà dans la base de données")

    print("Produits insérés avec succès !") 
else:
    print(f"Erreur lors de la requête : {response.status_code}")

@app.route('/', methods=['GET'])
def get_products():
    products = Product.select().dicts()
    return jsonify({"products": list(products)})


@app.route('/order/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = Order.get_or_none(Order.id == order_id)
    # Vérifie si la commande est en cache dans Redis
    order_cache_key = f"order:{order_id}"
    order_cache_data = r.get(order_cache_key)

    if order_cache_data:
        order_data = json.loads(order_cache_data)
        return jsonify({'order': order_data}), 200

    # Si la commande n'est pas en cache, la récupérer depuis la base de données Postgres
    order = Order.get_or_none(Order.id == order_id)
    if order:
        order_data = {
            'id': order.id,
            'total_price': order.total_price,
            'shipping_price': order.shipping_price,
            'email': order.email,
            'paid': order.paid,
            'product': {
                'id': order.orderItem.product.id if order.orderItem.product else None,
                'quantity': order.orderItem.quantity
            },
            'transaction_id': order.transaction_id.id if order.transaction_id else None,
            'credit_card_id': order.credit_card_id.credit_card_id if order.credit_card_id else None,
            'shipping_id': order.shipping_id.shipping_id if order.shipping_id else None,
        }
        return jsonify({'order': order_data}), 200
    else:
        abort(404, description=f"La commande avec l'ID {order_id} n'a pas été trouvée.")

def calcul_ship(produit, quant):
    poids=produit.weight
    poids_Total=poids*quant
    if poids_Total<500:
        return(5)
    if(500<poids_Total<2000):
        return(10)
    if poids_Total>2000:
        return(25)
    return(0)

def calcul_tot_price(produit,quant):
    prix_unit=produit.price
    return(prix_unit*quant)



@app.route('/order', methods=['POST'])
def post_order():
    print("Requête POST reçue")
    product_data = request.json['product']
    if 'product' not in request.json or 'id' not in product_data or 'quantity' not in product_data:
        return jsonify({
            "errors": {
                "product": {
                    "code": "missing-fields",
                    "name": "La création d'une commande nécessite un produit"
                }
            }
        }), 422 


    product_id = product_data['id']
    quantity = product_data['quantity']

    if quantity < 1:
        return jsonify({
            "errors": {
                "product": {
                    "code": "missing-fields",
                    "name": "La quantité doit être supérieure ou égale à 1"
                }
            }
        }), 422  
    
    product = Product.get_or_none(id=product_id)
    if product:
        if not product.in_stock:
            return jsonify({
                "errors": {
                    "product": {
                        "code": "out-of-inventory",
                        "name": "Le produit demandé n'est pas en inventaire"
                    }
                }
            }), 422 
        
        ship_price=calcul_ship(product, quantity)
        prix_tot=calcul_tot_price(product, quantity)
        amount_charged=ship_price+prix_tot

        order_item = OrderItem.create(product=product, quantity=quantity)
        transac = Transaction.create(amount_charged=amount_charged, success=False)
        new_order = Order.create(total_price=prix_tot, shipping_price=ship_price, paid=False, orderItem=order_item, transaction_id=transac.id)

          # Mise en cache de la commande dans Redis
        order_cache_key = f"order:{new_order.id}"
        order_cache_data = {
            'id': new_order.id,
            'total_price': new_order.total_price,
            'shipping_price': new_order.shipping_price,
            'email': new_order.email,
            'paid': new_order.paid,
            'product': {
                'id': new_order.orderItem.product.id if new_order.orderItem.product else None,
                'quantity': new_order.orderItem.quantity
            },
            'transaction_id': new_order.transaction_id.id if new_order.transaction_id else None,
            'credit_card_id': new_order.credit_card_id.id if new_order.credit_card_id else None,
            'shipping_id': new_order.shipping_id.id if new_order.shipping_id else None,
        }
        r.set(order_cache_key, json.dumps(order_cache_data))

        return redirect(url_for('get_order', order_id=new_order.id), code=302)
    else:
        return('il ny a pas de produit avec cet id')




@app.route('/order/<int:order_id>', methods=['PUT'])
def put_ship_info_and_cc(order_id):
    order = Order.get_or_none(Order.id == order_id)
    print(request.json)
    #CHECK SI L'ORDER DEMANDEE EXISTE
    if order:
        #1 CHECK SI LES INFOS DE SHIPPING SONT VIDES PUIS LUI EN AJOUTE
        if order.shipping_id==None:
            order_data=request.json['order']
            shipping_info_data = order_data['shipping_information']
            if 'email' not in order_data or 'country' not in shipping_info_data or 'address' not in shipping_info_data or 'postal_code' not in shipping_info_data or 'city' not in shipping_info_data or 'province' not in shipping_info_data:
                return jsonify({
                "errors" : {
                    "order": {
                        "code": "missing-fields",
                        "name": "Il manque un ou plusieurs champs qui sont obligatoires"
                    }
                }
            }), 422 

            else:
                ship = ShippingInfo.create(
                    shipping_information_country=shipping_info_data.get('country'),
                    shipping_information_address=shipping_info_data.get('address'),
                    shipping_information_postal_code=shipping_info_data.get('postal_code'),
                    shipping_information_city=shipping_info_data.get('city'),
                    shipping_information_province=shipping_info_data.get('province')
                )
                ship_id = ship.shipping_id
                order.shipping_id = ship_id
                order.email = order_data.get('email', order.email)
                order.save()
                order_data = {
                    'id': order.id,
                    'total_price': order.total_price,
                    'shipping_price': order.shipping_price,
                    'email': order.email,
                    'paid': order.paid,
                    'product': {
                        'id': order.orderItem.product.id if order.orderItem.product else None,
                        'quantity': order.orderItem.quantity
                    },
                    'transaction_id': order.transaction_id.id if order.transaction_id else None,
                    'credit_card_id': order.credit_card_id.credit_card_id if order.credit_card_id else None,
                    "shipping_information" : {
                        "country" : ship.shipping_information_country,
                        "address" : ship.shipping_information_address,
                        "postal_code" : ship.shipping_information_postal_code,
                        "city" : ship.shipping_information_city,
                        "province" : ship.shipping_information_province
                    },
                }
                return jsonify({'order': order_data}), 200
        #FIN DU CHECK INFO SHIPPING, RETURN FORCEMENT QQCH
        
        #2 CHECK SI LES INFOS DE SHIPPING SONT REMPLIS ET QUE LEMAIL EST PRESENT AVANT DE REMPLIR LES INFOS DE CARTE
        
        elif order.credit_card_id==None:
            if order.shipping_id==None or order.email==None:
                return jsonify({
                    "errors" : {
                        "order": {
                            "code": "missing-fields",
                            "name": "Les informations du client sont nécessaire avant d'appliquer une carte de crédit"
                        }
                    }
                }), 422
            else:
                credit_card_data = request.json['credit_card']
                if 'name' not in credit_card_data or 'number' not in credit_card_data or 'expiration_year' not in credit_card_data or 'cvv' not in credit_card_data or 'expiration_month' not in credit_card_data:
                    return jsonify({
                    "errors" : {
                        "order": {
                            "code": "missing-fields",
                            "name": "Il manque un ou plusieurs champs qui sont obligatoires"
                        }
                    }
                }), 422 
                elif credit_card_data.get('number')=='4000 0000 0000 0002':
                    return jsonify({
                        "credit_card": {
                            "code": "card-declined",
                            "name": "La carte de crédit a été déclinée."
                        }
                    })
                elif credit_card_data.get('number')!='4000 0000 0000 0002' and credit_card_data.get('number')!='4242 4242 4242 4242':
                    return jsonify({
                        "credit_card": {
                            "code": "card-declined",
                            "name": "numero de carte invalide"
                        }
                    })
                elif credit_card_data.get('number')=='4242 4242 4242 4242':
                    ship=order.shipping_id
                    cc=CreditCard.create(credit_card_owner = credit_card_data.get('name'), credit_card_number = credit_card_data.get('number'), credit_card_expiration_year = credit_card_data.get('expiration_year'), credit_card_expiration_month = credit_card_data.get('expiration_month'), credit_card_ccv = credit_card_data.get('cvv'))
                    order.credit_card_id=cc.credit_card_id
                    order.paid=True
                    order.save()
                    order_data = {
                        'id': order.id,
                        'total_price': order.total_price,
                        'shipping_price': order.shipping_price,
                        'email': order.email,
                        'paid': order.paid,
                        'product': {
                            'id': order.orderItem.product.id if order.orderItem.product else None,
                            'quantity': order.orderItem.quantity
                        },
                        'transaction_id': order.transaction_id.id if order.transaction_id else None,
                        'credit_card': {
                            "name" : cc.credit_card_owner,
                            "number" : cc.credit_card_number,
                            "expiration_year" : cc.credit_card_expiration_year,
                            "cvv" : cc.credit_card_ccv,
                            "expiration_month" : cc.credit_card_expiration_month
                        },
                        "shipping_information" : {
                            "country" : ship.shipping_information_country,
                            "address" : ship.shipping_information_address,
                            "postal_code" : ship.shipping_information_postal_code,
                            "city" : ship.shipping_information_city,
                            "province" : ship.shipping_information_province
                        },
                    }
                    return jsonify({'order': order_data}), 200
        #FIN DU CHECK POUR AJOUTER LES INFOS DE CARTES, RETOURNE FORCEMENT QQCH

        #3 CHECK SI LES INFOS DE CREDIT CARD SONT REMPLIES ET DEMANDE AU SERVEUR DISTANT DE VALIDER LA TRANSACTION           
        elif order.credit_card_id!=None and order.paid==True:   
            credit_card_data = {
                "name": order.credit_card_id.credit_card_owner,
                "number": order.credit_card_id.credit_card_number,
                "expiration_year": order.credit_card_id.credit_card_expiration_year,
                "cvv": order.credit_card_id.credit_card_ccv,
                "expiration_month": order.credit_card_id.credit_card_expiration_month
            }

            amount_charged = order.total_price + order.shipping_price

            payment_data = {
                "credit_card": credit_card_data,
                "amount_charged": amount_charged
            }

            response = requests.post(
                "http://dimprojetu.uqac.ca/~jgnault/shops/pay/",
                json=payment_data,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                payment_result = response.json()
                order.transaction_id.success = payment_result["transaction"]["success"]
                order.transaction_id.amount_charged = payment_result["transaction"]["amount_charged"]
                order.paid = True
                order.save()

                # Gestion des erreurs de paiement
                if not payment_result["transaction"]["success"]:
                    order.transaction_id.error = {
                        "code": payment_result["transaction"]["error"]["code"],
                        "name": payment_result["transaction"]["error"]["name"]
                    }
                    order.transaction_id.save()

                return jsonify({
                    "credit_card" : {
                        "name": order.credit_card_id.credit_card_owner,
                        "number": order.credit_card_id.credit_card_number,
                        "expiration_year": order.credit_card_id.credit_card_expiration_year,
                        "cvv": order.credit_card_id.credit_card_ccv,
                        "expiration_month": order.credit_card_id.credit_card_expiration_month
                    },
                    "transaction": {
                        "id": order.transaction_id.id,
                        "success": True,
                        "amount_charged": order.transaction_id.amount_charged
                    }
                }), 200
            
        #FIN DU CHECK POUR EFFECTUER LA TRANSACTION, DOIT RETOURNER QQCH
        else:
            return jsonify({
                "errors" : {
                    "order": {
                        "code": "already-paid",
                        "name": "La commande a déjà été payée."
                        }
                }
            }), 422
    #SI L'ORDER N'A PAS ETE TROUVEE
    
    else:
        abort(404, description=f"La commande avec l'ID {order_id} n'a pas été trouvée.")


if __name__ == "__main__":
    app.run(debug=True) 
