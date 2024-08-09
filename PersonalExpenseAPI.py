from flask import Flask, jsonify, request
from pymongo import MongoClient
import functools
from flask_cors import CORS


app = Flask(__name__)

#CORS for all routes
CORS(app)

# OR, Enable CORS for specific origins
# CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

# Define your secure token
SECURE_TOKEN = 'my_secure_token'

# MongoDB connection
# client = MongoClient('mongodb+srv://Deep0902:Siemens123%40@deep0902.214cie0.mongodb.net/?retryWrites=true&w=majority&appName=Deep0902')
client = MongoClient('mongodb://localhost:27017/')
db = client.expense_tracker
users_collection = db.users
admin_collection = db.admin
expenses_collection = db.expenses

# Function to convert MongoDB users data to JSON
def users_to_json(users):
    return {
        'user_email': users['user_email'],
        'user_pass': users['user_pass'],
        'user_id': users['user_id'],
        'user_name': users['user_name'],
        'wallet':users['wallet'],
        'profile_img':users['profile_img']
    }

# Function to convert MongoDB expense data to JSON
def expenses_to_json(expenses):
    return {
        'user_id': expenses['user_id'],
        'transaction_no': expenses['transaction_no'],
        'transaction_type': expenses['transaction_type'],
        'title': expenses['title'],
        'amount': expenses['amount'],
        'category': expenses['category'],
        'date': expenses['date']
    }

# Function to convert MongoDB admin data to JSON
def admin_to_json(admin):
    return {
        'admin_pass': admin['admin_pass'],
        'admin_id': admin['admin_id']
    }

# Authentication decorator
def token_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({"message": "Unauthorized"}), 401

        token_value = token.split()[1] if len(token.split()) > 1 else None
        if token_value != SECURE_TOKEN:
            return jsonify({"message": "Unauthorized"}), 401

        return f(*args, **kwargs)
    return decorated_function
#-------------------------------------------------------ADMIN----------------------------------------------
# GET all admin
@app.route('/api/admin', methods=['GET'])
@token_required
def get_admin():
    admin = list(admin_collection.find())
    return jsonify([admin_to_json(admin) for admin in admin])

# GET admin validation
@app.route('/api/admin', methods=['POST'])
@token_required
def validate_admin():
    data = request.json
    admin_id = data.get('admin_id')
    admin_pass = data.get('admin_pass')

    if not admin_id or not admin_pass:
        return jsonify({"message": "Admin ID and password required"}), 400

    admin = admin_collection.find_one({'admin_id': admin_id, 'admin_pass': admin_pass})
    if admin:
        return jsonify({"valid": True}), 200
    else:
        return jsonify({"valid": False}), 401

# GET admin by id
@app.route('/api/admin/<string:admin_id>', methods=['GET'])
@token_required
def get_admin_id(admin_id):
    admin = admin_collection.find_one({'admin_id': admin_id})
    if admin is None:
        return jsonify({"message": "Admin not found"}), 404
    return jsonify(admin_to_json(admin))


#------------------------------------------------------USERS----------------------------------------------

# GET all users
@app.route('/api/users', methods=['GET'])
@token_required
def get_users():
    users = list(users_collection.find())
    return jsonify([users_to_json(user) for user in users])

# GET a single user by ID
@app.route('/api/users/<string:user_email>', methods=['GET'])
@token_required
def get_user(user_email):
    user = users_collection.find_one({'user_email': user_email})
    if user is None:
        return jsonify({"message": "User not found"}), 404
    return jsonify(users_to_json(user))

# API endpoint to create a new user
@app.route('/api/users', methods=['POST'])
@token_required
def create_user():
    # Check if the request contains all required fields
    if not request.json or 'user_pass' not in request.json or 'user_name' not in request.json or 'user_email' not in request.json:
        return jsonify({"message": "Enter all details"}), 400

    user_email = request.json['user_email']
    
    # Determine new user_id
    if 'user_id' in request.json:
        new_user_id = request.json['user_id']
    else:
        last_user = list(users_collection.find().sort('user_id', -1).limit(1))
        new_user_id = last_user[0]['user_id'] + 1 if len(last_user) > 0 else 1

    # Check for duplicate user_id or user_email
    if users_collection.find_one({'user_id': new_user_id}):
        return jsonify({"message": "User with this user ID already exists"}), 409
    if users_collection.find_one({'user_email': user_email}):
        return jsonify({"message": "User with this email already exists"}), 409
    
    # Create new user
    new_user = {
        'user_id': new_user_id,
        'user_pass': request.json['user_pass'],
        'user_email': user_email,
        'user_name': request.json['user_name'],
        'wallet': 0,
        'profile_img':1
    }
    result = users_collection.insert_one(new_user)
    new_user['_id'] = str(result.inserted_id)
    return jsonify(new_user), 201

# API endpoint to update an existing user
@app.route('/api/users/<int:user_id>', methods=['PUT'])
@token_required
def update_user(user_id):
    user = users_collection.find_one({'user_id': user_id})
    if user is None:
        return jsonify({"message": "User does not exist"}),404
    
    update_data = {
        'user_pass': request.json.get('user_pass', user['user_pass']),
        'user_email': request.json.get('user_email', user['user_email']),
        'user_name': request.json.get('user_name', user['user_name']),
        'profile_img': request.json.get('profile_img', user['profile_img']),
        'wallet': request.json.get('wallet', user['wallet'])
    }
    users_collection.update_one({'user_id': user_id}, {'$set': update_data})
    updated_user = users_collection.find_one({'user_id': user_id})
    return jsonify(users_to_json(updated_user))

# DELETE a user along with all their expenses
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@token_required
def delete_user(user_id):
    # First, delete all expenses associated with the user
    expenses_result = expenses_collection.delete_many({'user_id': user_id})

    # Then, delete the user
    user_result = users_collection.delete_one({'user_id': user_id})

    if user_result.deleted_count == 0:
        return jsonify({"message": "User not found"}), 404

    if expenses_result.deleted_count > 0:
        return jsonify({
            "message": "User and associated expenses deleted successfully",
            "expenses_deleted": expenses_result.deleted_count
        }), 200
    else:
        return jsonify({
            "message": "User deleted successfully, but no associated expenses found"
        }), 200


# GET user validation
@app.route('/api/user', methods=['POST'])
@token_required
def validate_user():
    data = request.json
    user_email = data.get('user_email')
    user_pass = data.get('user_pass')

    if not user_email or not user_pass:
        return jsonify({"message": "User ID and password required"}), 400

    user = users_collection.find_one({'user_email': user_email, 'user_pass': user_pass})
    if user:
        return jsonify({"valid": True}), 200
    else:
        return jsonify({"valid": False}), 401

#---------------------------------------------------------EXPENSES-----------------------------------------------
# GET all expenses
@app.route('/api/expenses', methods=['GET'])
@token_required
def get_expenses():
    expenses = list(expenses_collection.find())
    return jsonify([expenses_to_json(expenses) for expenses in expenses])

#Get all expenses for specific uesr
@app.route('/api/expenses/<int:user_id>', methods=['GET'])
@token_required
def get_expenses_for_user(user_id):
    expenses = list(expenses_collection.find({'user_id': user_id}))
    return jsonify([expenses_to_json(expense) for expense in expenses])

#Get expenses by id and transaction no
@app.route('/api/expenses/<int:user_id>/<int:transaction_no>', methods=['GET'])
@token_required
def get_expense_id_with_transaction(user_id, transaction_no):
    try:
        expense = expenses_collection.find_one({'user_id':user_id, 'transaction_no': transaction_no})
        if expense is None:
            return jsonify({"message": "Expense not found"}), 404
        return jsonify(expenses_to_json(expense))
    except Exception as e:
        return jsonify({"message": "Error has occured", "error": str(e)}), 400
    
# DELETE expense by transaction_id and user_id
@app.route('/api/expenses/<int:user_id>/<int:transaction_no>', methods=['DELETE'])
@token_required
def delete_expense(user_id, transaction_no):
    expense = expenses_collection.find_one({'user_id':user_id, 'transaction_no': transaction_no})
    if expense is None:
        return jsonify({"message": "Expense not found"}), 404
    
    result = expenses_collection.delete_one({'user_id': user_id, 'transaction_no': transaction_no})
    if result.deleted_count == 1:
        return jsonify({"message": "Expense deleted successfully"}), 200
    else:
        return jsonify({"message": "Failed to delete expense"}), 500
    
# EDIT expense by transaction_no and user_id
@app.route('/api/expenses/<int:user_id>/<int:transaction_no>', methods=['PUT'])
@token_required
def update_expense(user_id, transaction_no):
    expense = expenses_collection.find_one({'user_id':user_id, 'transaction_no': transaction_no})
    if expense is None:
        return jsonify({"message": "Expense not found"}), 404
    update_expense_data={
        'transaction_type': request.json.get('transaction_type', expense['transaction_type']),
        'title': request.json.get('title',expense['title']),
        'amount': request.json.get('amount',expense['amount']),
        'category': request.json.get('category',expense['category']),
        'date': request.json.get('date',expense['date'])
    }
   
    expenses_collection.update_one({'user_id':user_id, 'transaction_no': transaction_no}, {'$set': update_expense_data})
    updated_expense = expenses_collection.find_one({'user_id':user_id, 'transaction_no': transaction_no})
    return jsonify(expenses_to_json(updated_expense))

#Create a new expense
@app.route('/api/expenses', methods=['POST'])
@token_required
def create_expense():
    if not request.json or 'user_id' not in request.json or 'transaction_type' not in request.json or 'title' not in request.json or 'amount' not in request.json or 'category' not in request.json or 'date' not in request.json:
        return jsonify({"message": "Add complete expense data"}), 400
    
    # Find the highest transaction_no for the given user_id
    user_id = request.json['user_id']
    highest_transaction = expenses_collection.find({'user_id': user_id}).sort("transaction_no", -1).limit(1)
    highest_transaction = list(highest_transaction)

    if highest_transaction:
        transaction_no = highest_transaction[0]['transaction_no'] + 1
    else:
        transaction_no = 1
    
    #Update new data
    new_expense = {
        'transaction_no': transaction_no,
        'user_id': user_id,
        'transaction_type': request.json['transaction_type'],
        'title': request.json['title'],
        'amount': request.json['amount'],
        'category': request.json['category'],
        'date': request.json['date']
    }

    #Add to db
    result = expenses_collection.insert_one(new_expense)
    new_expense['_id'] = str(result.inserted_id)
    return jsonify(expenses_to_json(new_expense)), 201

#------------------------------------API END----------------------------------
# Run the app with SSL context
# app.run(host="0.0.0.0", port=5000, debug=True, ssl_context=("cert.pem", "key.pem"))
# app.run(host="0.0.0.0", port=5000, debug=True, ssl_context=("adhoc"))

if __name__ == '__main__':
    app.run(debug=True)
