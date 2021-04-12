import jwt
import uuid
import datetime

from functools         import wraps
from flask             import Flask, request, jsonify, make_response
from flask_sqlalchemy  import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

app.config['SECRET_KEY']='THISISSECRET'
app.config['SQLALCHEMY_DATABASE_URI']='sqlite:////home/hyeseong/Projects/pretty_printed/flask_api_example/todo.db'

db = SQLAlchemy(app)

class User(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True)
    name      = db.Column(db.String(50))
    password  = db.Column(db.String(80))
    admin     = db.Column(db.Boolean)
    todo      = db.relationship('Todo', backref='user', lazy=True)


class Todo(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    text     = db.Column(db.String(50))
    complete = db.Column(db.Boolean)
    user_id  = db.Column(db.Integer, db.ForeignKey('user.id'))

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], 'HS256')
            current_user = User.query.filter_by(public_id=data['public_id']).first()
        except:
            return jsonify({'message':'Token is invalid!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/users', methods=['GET'])
@token_required
def get_all_users(current_user):
    if not current_user.admin:
        return jsonify({'message':'Can not perform the function!'})

    output = [{
                "id"        : user.id,
                "public_id" : user.public_id,
                "name"      : user.name,
                "password"  : user.password,
                "admin"     : user.admin,
            }for user in User.query.all()]
    return jsonify({'users': output})

@app.route('/users/<public_id>', methods=['GET'])
@token_required
def get_one_user(current_user, public_id):
    if not current_user.admin:  # 
        return jsonify({'message':'Can not perform the function!'})
    # user = User.query.filter_by(public_id=public_id).first_or_404() # 404 예외 처리 1
    
    user = User.query.filter_by(public_id=public_id).first() # 404 예외 처리 2
    if not user:
        return jsonify({'message':'No user found!'})

    return jsonify({
                    "id"        : user.id,
                    "public_id" : user.public_id,
                    "name"      : user.name,
                    "password"  : user.password,
                    "admin"     : user.admin,
                    "todo"      : user.todo
                })
    
@app.route('/user', methods=['POST'])
def create_user():
    data = request.get_json()

    new_user = User(
        public_id = str(uuid.uuid4()),
        name      = data['name'],
        password  = generate_password_hash(data['password'], method='sha256'),
        admin     = False
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'New User Created!'})

@app.route('/users/<public_id>', methods=['PUT'])
@token_required
def promote_user(current_user, public_id):
    if not current_user.admin:
        return jsonify({'message':'Can not perform the function!'})
    user = User.query.filter_by(public_id=public_id).first_or_404()
    user.admin = True
    db.session.commit()
    return jsonify({'message':'The user has been promoted!'})

@app.route('/users/<public_id>', methods=['DELETE'])
@token_required
def delete_user(current_user, public_id):
    if not current_user.admin:
        return jsonify({'message':'Can not perform the function!'})
    user = User.query.filter_by(public_id=public_id).first_or_404()
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message':'The user has been deleted!'})

@app.route('/login', methods=['GET'])
def login():
    auth = request.authorization
    if not auth.username or not auth.password:
        return make_response(
                'Could not verify',
                401, 
                {'WWW-Authenticate' : 'Basic realm="Login required!"'})

    user = User.query.filter_by(name=auth.username).first()
    if not user:
        return make_response(
            'Could not verify',
            401, 
            {'WWW-Authenticate' : 'Basic realm="Login required!"'})
    
    if check_password_hash(user.password, auth.password):
        token = jwt.encode({
                            'public_id' : user.public_id, 
                            'exp'       : datetime.datetime.utcnow() + datetime.timedelta(seconds=60*60*24)
                            }, app.config['SECRET_KEY']
                            , algorithm='HS256')
        return jsonify({'token': token})
    return make_response(
        'Could not verify',
        401, 
        {'WWW-Authenticate' : 'Basic realm="Login required!"'})
    
@app.route('/todos', methods=['GET'])
@token_required
def get_all_todos(current_user):
    return jsonify([{
                  'id'        : todo.id,
                  'text'      : todo.text,
                  'complete'  : todo.complete,
            }for todo in Todo.query.filter_by(user_id=current_user.id).all()]), 200
    

@app.route('/todo/<todo_id>', methods=['GET'])
@token_required
def get_one_todo(current_user, todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first()

    if not todo:
        return jsonify({'message':'No todo found!'})
    output = {
                'id'        : todo.id,
                'text'      : todo.text,
                'complete'  : todo.complete,
            }
    return jsonify({'message':output}), 200

@app.route('/todo', methods=['POST'])
@token_required
def create_todo(current_user):
    data = request.json
    new_todo = Todo(text=data['text'], complete=False, user_id=current_user.id)
    db.session.add(new_todo)
    db.session.commit()
    return jsonify({'message':new_todo.text}), 201

@app.route('/todo/<todo_id>', methods=['PUT'])
@token_required
def complete_todo(current_user, todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first()

    if not todo:
        return jsonify({'message':'No todo found!'})
    todo.complete = True if not todo.complete else False
    output = {
                'id'        : todo.id,
                'text'      : todo.text,
                'complete'  : todo.complete,
            }
    db.session.commit()
    return jsonify({'message':output}), 200
    

@app.route('/todo/<todo_id>', methods=['DELETE'])
@token_required
def delete_todo(current_user, todo_id):
    request
    todo = Todo.query.filter_by(id=todo_id, user_id=current_user.id).first()

    if not todo:
        return jsonify({'message':'No todo found!'})
    
    db.session.delete(todo)
    db.session.commit()            
    return jsonify({'message':'Todo has been deleted'}), 200
    


if __name__ == '__main__':
    app.run(debug=True)
