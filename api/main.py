from flask_sqlalchemy import SQLAlchemy
from flask import Flask, request, jsonify
from flask_mail import Mail, Message
import uuid, datetime, joblib, aiohttp
import numpy as np
import tensorflow as tf

app = Flask(__name__)
app.config.from_pyfile('config.py')
db = SQLAlchemy(app)

# API Ninja config
my_api_key = "B+Rpc1sVtV5cDnWYOXuiEw==uwuV9tafPifkLadt" # Personal Secret API Key for Tugas 01 LAW
headers = { "X-Api-Key": my_api_key }

# Email config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'tugas2law.2006526106@gmail.com'
app.config['MAIL_PASSWORD'] = 'xjjnawosejawcvax'
mail = Mail(app)

# Classes
class UserAccount(db.Model):
    id = db.Column(db.String(8), primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    fullname = db.Column(db.String(120), nullable=False)
    birthdate = db.Column(db.Date)
    gender = db.Column(db.String(10))
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    activity_level = db.Column(db.Integer)

    def __init__(self, username, fullname, birthdate=None, gender=None, height=None, weight=None, activity_level=None):
        self.id = str(uuid.uuid4())[:8]
        self.username = username
        self.fullname = fullname
        self.birthdate = birthdate
        self.gender = gender
        self.height = height
        self.weight = weight
        self.activity_level = activity_level


# App routes
@app.route('/')
def index():
    return jsonify({'message': 'Welcome to daily nutrition intake monitoring!'}), 200


@app.route('/register', methods=['POST'])
def register_user():
    data = request.json
    if not data or 'username' not in data or 'fullname' not in data:
        return jsonify({'message': 'Missing required fields'}), 400
    
    user_account = UserAccount(
        username=data['username'],
        fullname=data['fullname'],
        gender=data.get('gender'),
        height=data.get('height'),
        weight=data.get('weight'),
        birthdate=data.get('birthdate'),
        activity_level=data.get('activity_level')
    )

    db.session.add(user_account)

    try:
        db.session.commit()
        return jsonify({'message': 'User successfully registered'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'User registration failed', 'error': str(e)}), 500


@app.route('/profile/<username>')
def profile(username):
    user_account = UserAccount.query.filter_by(username=username).first()
    if user_account:
        user_profile = {
            'username': user_account.username,
            'fullname': user_account.fullname,
            'gender': user_account.gender,
            'height': user_account.height,
            'weight': user_account.weight,
            'birthdate': user_account.birthdate.isoformat() if user_account.birthdate else None,
            'activity_level': user_account.activity_level
        }
        return jsonify(user_profile), 200
    else:
        return jsonify({'message': 'User not found'}), 404


@app.route('/profile/<username>', methods=['PUT'])
def edit_profile(username):
    user_account = UserAccount.query.filter_by(username=username).first()
    if not user_account:
        return jsonify({'message': 'User not found'}), 404

    data = request.json
    if not data:
        return jsonify({'message': 'Missing data'}), 400

    if 'fullname' in data:
        user_account.fullname = data['fullname']
    if 'gender' in data:
        user_account.gender = data['gender']
    if 'height' in data:
        user_account.height = data['height']
    if 'weight' in data:
        user_account.weight = data['weight']
    if 'birthdate' in data:
        user_account.birthdate = data['birthdate']
    if 'activity_level' in data:
        user_account.activity_level = data['activity_level']

    db.session.commit()

    return jsonify({'message': 'Profile has been updated'}), 200


@app.route('/delete-user/<username>', methods=['DELETE'])
def delete_user(username):
    user_account = UserAccount.query.filter_by(username=username).first()
    if not user_account:
        return jsonify({'message': 'User not found'}), 404

    db.session.delete(user_account)

    try:
        db.session.commit()
        return jsonify({'message': f'User {username} has been deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Delete user failed', 'error': str(e)}), 500


def calculate_age(birthdate):
    today = datetime.date.today()
    age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    return age


def calculate_calorie_need(bmr, activity_level):
    multiplier = 0

    if activity_level == 1:
        multiplier = 1.2
    elif activity_level == 2:
        multiplier = 1.375
    elif activity_level == 3:
        multiplier = 1.55
    elif activity_level == 4:
        multiplier = 1.725
    else:
        multiplier = 1.9

    return bmr*multiplier


@app.route('/daily-nutrition-needs/<username>')
def calculate_user_daily_nutrition_needs(username):
    user_account = UserAccount.query.filter_by(username=username).first()
    if not user_account:
        return jsonify({'message': 'User not found'}), 404

    user_age = calculate_age(user_account.birthdate)
    bmr = 0
    
    if user_account.gender.lower() == "male":
        bmr = 66.5 + (13.75*user_account.weight) + (5.003*user_account.height) - (6.75*user_age)
    else:
        bmr = 655.1 + (9.563*user_account.weight) + (1.85*user_account.height) - (4.676*user_age)
    
    calorie_need = calculate_calorie_need(bmr, user_account.activity_level)
    protein_need = 0.75*user_account.weight
    fat_need = 0.2*calorie_need
    fiber_need = 25 # in gram
    carbohydrate_need = 0.45*calorie_need

    return jsonify({
        'username': username,
        'calorie_need': calorie_need,
        'protein_need': protein_need,
        'fat_need': fat_need,
        'fiber_need': fiber_need,
        'carbohydrate_need': carbohydrate_need
    }), 200


async def get_exercises(exercise_name):
    print(f"get_exercises({exercise_name}) is called!")
    api_url = f"https://api.api-ninjas.com/v1/exercises?name={exercise_name}"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            return await response.json()
        

async def get_calories_burned(activity_name):
    print(f"get_calories_burned({activity_name}) is called!")
    api_url = f"https://api.api-ninjas.com/v1/caloriesburned?activity={activity_name}"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            return await response.json()


async def get_foods_nutrition(food_names):
    print(f"get_foods_nutrition({food_names}) is called!")
    api_url = f"https://api.api-ninjas.com/v1/nutrition?query={food_names}"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            return await response.json()


@app.route('/call-API-Ninja-APIs-async', methods=['POST'])
async def call_API_Ninja_APIs_with_async():
    data = request.json
    exercises_response = await get_exercises(data['exercise_name'])
    calories_burned_response = await get_calories_burned(data['activity_name'])
    foods_nutrition_response = await get_foods_nutrition(data['food_names'])

    return jsonify({
        'message': 'Successfully called 3 API Ninja APIs asynchronously!',
        'exercises_response': exercises_response,
        'calories_burned_response': calories_burned_response,
        'foods_nutrition_response': foods_nutrition_response
    }), 200


async def get_user_daily_nutrition_needs(url):
    print(f"get_user_daily_nutrition_needs({url}) is called!")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()


@app.route('/today-nutrition-intake/<username>', methods=['POST'])
async def check_user_today_nutrition_intake(username):
    print(f"check_user_today_nutrition_intake({username}) is called!")
    calorie_intake = 0
    protein_intake = 0
    fat_intake = 0
    fiber_intake = 0
    carbohydrate_intake = 0

    data = request.json
    food_names = ' or '.join(data.keys())
    
    foods_nutrition_response = await get_foods_nutrition(food_names)
    if 'error' in foods_nutrition_response:
        return {"error": foods_nutrition_response['error']}, 500

    for food_nutrition in foods_nutrition_response:
        serving = data[food_nutrition['name'].lower()]/100
        calorie_intake += food_nutrition['calories'] * serving
        protein_intake += food_nutrition['protein_g'] * serving
        fat_intake += food_nutrition['fat_total_g'] * serving
        fiber_intake += food_nutrition['fiber_g'] * serving
        carbohydrate_intake += food_nutrition['carbohydrates_total_g'] * serving

    base_url = request.base_url.split('/today')[0]
    url = f"{base_url}/daily-nutrition-needs/{username}"
    user_daily_nutrition_needs = await get_user_daily_nutrition_needs(url)

    lack_nutritions = []
    lack_nutritions_dict = {}
    if (calorie_intake < user_daily_nutrition_needs['calorie_need']):
        lack_nutritions.append('calorie')
        lack_nutritions_dict['calorie'] = calorie_intake - user_daily_nutrition_needs['calorie_need']
    if (protein_intake < user_daily_nutrition_needs['protein_need']):
        lack_nutritions.append('protein')
        lack_nutritions_dict['protein'] = protein_intake - user_daily_nutrition_needs['protein_need']
    if (fat_intake < user_daily_nutrition_needs['fat_need']):
        lack_nutritions.append('fat')
        lack_nutritions_dict['fat'] = fat_intake - user_daily_nutrition_needs['fat_need']
    if (fiber_intake < user_daily_nutrition_needs['fiber_need']):
        lack_nutritions.append('fiber')
        lack_nutritions_dict['fiber'] = fiber_intake - user_daily_nutrition_needs['fiber_need']
    if (carbohydrate_intake < user_daily_nutrition_needs['carbohydrate_need']):
        lack_nutritions.append('carbohydrate')
        lack_nutritions_dict['carbohydrate'] = carbohydrate_intake - user_daily_nutrition_needs['carbohydrate_need']
    
    status = ""
    feedback = ""
    if len(lack_nutritions) == 0:
        status = "SUFFICIENT"
        feedback = f"Well done {username}! You have fulfilled your daily nutrition needs."
    else:
        status = "INSUFFICIENT"
        feedback = f"You still lack {', '.join(lack_nutritions)} intake today. Please consume more foods with high {', '.join(lack_nutritions)}. Stay healthy, {username}!"

    return jsonify({
        'username': username,
        'status': status,
        'lack_nutritions_in_gram': lack_nutritions_dict,
        'feedback': feedback
    }), 200


@app.route('/predict-cardiovascular-risk/<username>', methods=['POST'])
def predict_cardiovascular_risk(username):
    user_account = UserAccount.query.filter_by(username=username).first()
    if not user_account:
        return jsonify({'message': 'User not found'}), 404

    # Load model and scaler
    model = tf.keras.models.load_model('api/ml/heart_model.h5')
    scaler = joblib.load('api/ml/scaler.pkl')

    data = request.json

    age = calculate_age(user_account.birthdate)
    gender = 1 if user_account.gender == "Male" else 2
    height = user_account.height
    weight = user_account.weight
    ap_hi = data['ap_hi']
    ap_lo = data['ap_lo']
    cholesterol = data['cholesterol']
    glucose = data['glucose']
    smoke = data['smoke']
    alcohol = data['alcohol']
    active = 1 if user_account.activity_level > 2 else 0

    input_data = np.array(
        [[age, gender, height, weight, ap_hi, ap_lo, cholesterol, glucose, smoke, alcohol, active]]
    )
    data_scaled = scaler.transform(input_data)
    prediction = model.predict(data_scaled)
    prediction_bool = int(prediction[0][0] > 0.5)

    cardiovascular_risk = "Safe" if prediction_bool == 0 else "Aware"

    return jsonify({
        'username': username, 
        'cardiovascular_risk': cardiovascular_risk
    })


@app.route('/send-email', methods=['POST'])
def send_email():
    data = request.json
    recipient_email = data.get('recipient_email')

    if not recipient_email:
        return jsonify({'message': 'Missing recipient email'}), 400

    msg = Message(subject='Test Send Email',
                  sender=app.config['MAIL_USERNAME'],
                  recipients=[recipient_email])
    msg.body = 'Have a nice day!'
    mail.send(msg)

    return jsonify({'message': 'Email sent successfully!'})



if __name__ == '__main__':
    app.run(debug=True)