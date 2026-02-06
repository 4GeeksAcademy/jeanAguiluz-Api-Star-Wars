"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
from flask import Flask, request, jsonify, url_for
from flask_migrate import Migrate
from flask_swagger import swagger
from flask_cors import CORS
from utils import APIException, generate_sitemap
from admin import setup_admin
from models import db
from models import User, Favorites, Character, Planet, Vehicle, Post
#from models import Person

app = Flask(__name__)
app.url_map.strict_slashes = False

db_url = os.getenv("DATABASE_URL")
if db_url is not None:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace("postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/test.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

MIGRATE = Migrate(app, db)
db.init_app(app)
CORS(app)
setup_admin(app)

# Handle/serialize errors like a JSON object
@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code

# generate sitemap with all your endpoints
@app.route('/')
def sitemap():
    return generate_sitemap(app)

#ruta ejemplo
@app.route('/user', methods=['GET'])
def handle_hello():

    response_body = {
        "msg": "Hello, this is your GET /user response "
    }

    return jsonify(response_body), 200

# Antes defino un helper ya que aún no tenemos autenticación
def get_current_user():
    """
    Como no hay autenticación, usamos un usuario simple. Aquí devolvemos el primer usuario en la BD.
    """
    user = User.query.first()
    return user

# Listar Personajes
@app.route('/people', methods=['GET'])
def get_people():
    people = Character.query.all()
    # Si la lista está vacía, retorna una lista vacía y 200 
    response_body = list(map(lambda x: x.serialize(), people))
    return jsonify(response_body), 200

# Obtener un personaje por ID
@app.route('/people/<int:people_id>', methods=['GET'])
def get_single_people(people_id):
    person = Character.query.get(people_id)
    if person is None:
        return jsonify({"msg": f"Personaje con id {people_id} no encontrado"}), 404
    return jsonify(person.serialize()), 200

# Listar Planetas
@app.route('/planets', methods=['GET'])
def get_planets():
    planets = Planet.query.all()
    response_body = [planet.serialize() for planet in planets]
    return jsonify(response_body), 200

# Obtener planeta por ID
@app.route('/planets/<int:planet_id>', methods=['GET'])
def get_single_planet(planet_id):
    planet = Planet.query.get(planet_id)
    if planet is None:
        return jsonify({"msg": f"Planeta con id {planet_id} no encontrado"}), 404
    return jsonify(planet.serialize()), 200

#### 2. Edpoints de usuarios y favoritos del usuario ####

@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    response_body = [user.serialize() for user in users]
    return jsonify(response_body), 200

@app.route('/users/favorites', methods=['GET'])
def get_user_favorites():
    user = get_current_user()
    if not user:
        return jsonify({"msg": "Usuario no encontrado. Por favor cree primero un usuario en el admin"}), 404
    # Los fav están en user.favorites (en el modelo favorites)
    favs = [f.serialize() for f in user.favorites]
    return jsonify(favs), 200

### Añadir favoritos (POST) ###

def add_favorite(item_id, item_type, ModelClass):
    user = get_current_user()
    if not user:
        # Si no hay usuario logueado (o creado en la DB), retornamos error
        return jsonify({"msg": "Usuario no autenticado o no encontrado."}), 404
    # 1. Validar si el Character/Planet) existe
    item = ModelClass.query.get(item_id)
    if item is None:
        return jsonify({"msg": f"{item_type} con id {item_id} no encontrado"}), 404
    # 2. Revisar si ya es favorito para evitar duplicados
    existing_favorite = Favorites.query.filter_by(
        user_id=user.id,
        item_type=item_type,
        item_id=item_id
    ).first()

    if existing_favorite:
        return jsonify({"msg": f"El {item_type} ya es favorito del usuario"}), 400
    # 3. Crear y guardar nuevo favorito
    new_favorite = Favorites(
        user_id=user.id,
        item_type=item_type,
        item_id=item_id
    )
    db.session.add(new_favorite)
    try:
        db.session.commit()
        return jsonify({"msg": f"Favorite {item_type} añadido con éxito.", "favorite": new_favorite.serialize()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": f"Error al guardar favorito: {str(e)}"}), 500

@app.route('/favorite/planet/<int:planet_id>', methods=['POST'])
def add_favorite_planet(planet_id):
    return add_favorite(planet_id, 'planet', Planet)

@app.route('/favorite/people/<int:people_id>', methods=['POST'])
def add_favorite_people(people_id):
    return add_favorite(people_id, 'character', Character)

### Eliminar favoritos - DELETE
def delete_favorite(item_id, item_type):
    user = get_current_user()
    if not user:
        return jsonify({"msg": "Usuario no encontrado o no autenticado"})
    favorite = Favorites.query.filter_by(
        user_id=user.id,
        item_type=item_type,
        item_id=item_id
    ).first()
    if favorite is None:
        return jsonify({"msg": f"No se encontró el favorito {item_type} con id {item_id} para este usuario."}), 404

    # 2. Eliminar registro
    db.session.delete(favorite)
    try:
        db.session.commit()
        return jsonify({"msg": f"Favorite {item_type} eliminado con éxito."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": f"Error al eliminar favorito: {str(e)}"}), 500

@app.route('/favorite/planet/<int:planet_id>', methods=['DELETE'])
def delete_favorite_planet(planet_id):
    # Llama a la función genérica con los parámetros específicos
    return delete_favorite(planet_id, 'planet')

@app.route('/favorite/people/<int:people_id>', methods=['DELETE'])
def delete_favorite_people(people_id):
    # Llama a la función genérica con los parámetros específicos
    return delete_favorite(people_id, 'character')

# this only runs if `$ python src/app.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=PORT, debug=False)
