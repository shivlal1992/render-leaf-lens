import os
import tensorflow as tf
import numpy as np
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, session, make_response, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_PORT'] = 3307
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'mydatabase'
app.secret_key = 'key'

mysql = MySQL(app)

# Prevent caching
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


#-----------------Login/ SignIn-------------------
@app.route('/', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password,))
        account = cursor.fetchone()

        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            return render_template('index.html', msg="Login successful!", msg_icon="success", msg_title="Welcome", redirect_url=url_for('index'))
        else:
            return render_template('index.html', msg="Incorrect username/password!", msg_icon="error", msg_title="Login Failed")

    return render_template('index.html')


#---------------Logout------------
@app.route('/logout')
def logout():
    # Clear session data
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    
    # Create a response to redirect to the sign-in page
    response = make_response(redirect(url_for('signin')))
    
    # Add headers to prevent caching
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, public, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Add script to clear browser history
    response.set_data(response.get_data(as_text=True) + "<script>window.history.replaceState({}, '', '/signin');</script>")
    
    return response



#-------------------Register/ SignUp-----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    msg = ''
    msg_icon = ''
    msg_title = ''
    redirect_url = None
    
    if request.method == 'POST' and 'username' in request.form and 'email' in request.form and 'password' in request.form:
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()
        
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        email_account = cursor.fetchone()

        if account:
            msg = 'Account with this username already exists!'
            msg_icon = 'error'
            msg_title = 'Sign Up Failed'
            redirect_url = url_for('signup')
        
        elif email_account:
            msg = 'An account with this email already exists!'
            msg_icon = 'error'
            msg_title = 'Sign Up Failed'
            redirect_url = url_for('signup')

        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address!'
            msg_icon = 'error'
            msg_title = 'Sign Up Failed'
            redirect_url = url_for('signup')

        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers!'
            msg_icon = 'error'
            msg_title = 'Sign Up Failed'
            redirect_url = url_for('signup')

        elif not username or not password or not email:
            msg = 'Please fill out the form!'
            msg_icon = 'error'
            msg_title = 'Sign Up Failed'
            redirect_url = url_for('signup')
        else:
            cursor.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s)', (username, email, password))
            mysql.connection.commit()
            msg = 'You have successfully registered!'
            msg_icon = 'success'
            msg_title = 'Sign Up Successful'
            redirect_url = url_for('signin')
    
    elif request.method == 'POST':
        msg = 'Please fill out the form!'
        msg_icon = 'error'
        msg_title = 'Sign Up Failed'
    
    return render_template('user_signup.html', msg=msg, msg_icon=msg_icon, msg_title=msg_title, redirect_url=redirect_url)


#---------------Home page----------------
@app.route('/home')
def index():
    if 'loggedin' in session:
        return render_template('home.html', username=session['username'])
    else:
        return redirect(url_for('signin'))

#---------------User profile-------------
@app.route('/user_profile')
def user_profile():
    # Check if the user is logged in
    if 'loggedin' in session:
        # We need all the account info for the user so we can display it on the profile page
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE id = %s', (session['id'],))
        account = cursor.fetchone()
        # Show the profile page with account info
        return render_template('user_profile.html', account=account)
    # User is not logged in redirect to login page
    return redirect(url_for('index'))

#--------Diagnosis--------------
# Load the TensorFlow model
model = tf.keras.models.load_model('trained_model.keras')

@app.route('/diagnosis',  methods=['GET', 'POST'])
def diagnosis():
    if request.method == 'POST':
        test_image = request.files['image']
        image_path = os.path.join('uploads', test_image.filename)
        test_image.save(image_path)
        result_index = model_prediction(image_path)
        class_name = ['Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot',
                        'Corn_(maize)___healthy',
                        'Mango___Powdery_mildew',
                        'Mango_healthy',
                        'Potato___Early_blight',
                        'Potato___healthy',
                        'Rice_Brown_Spot',
                        'Rice_healthy']
        prediction = class_name[result_index]
        return render_template('diagnosis.html', prediction=prediction)
    return render_template('diagnosis.html')


def model_prediction(test_image):
    image = tf.keras.preprocessing.image.load_img(test_image, target_size=(128, 128))
    input_arr = tf.keras.preprocessing.image.img_to_array(image)
    input_arr = np.array([input_arr]) 
    predictions = model.predict(input_arr)
    return np.argmax(predictions)

@app.route('/service')
def service():
    return render_template('service.html')

@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM admin WHERE username = %s AND password = %s', (username, password,))
        accounts = cursor.fetchone()

        if accounts:
            session['loggedin'] = True
            session['id'] = accounts['id']
            session['username'] = accounts['username']
            return redirect(url_for('dashboard'))  # Redirect to dashboard after login
        else:
            return render_template('admin/admin_login.html', msg="Incorrect username/password!", msg_icon="error", msg_title="Login Failed")

    return render_template('admin/admin_login.html')


@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        username = session['username']
        return render_template('admin/dashboard.html', username=username)
    else:
        return redirect(url_for('admin'))
    
# @app.route('/adminlogout')
# def adminlogout():
#     session.pop('loggedin', None)
#     session.pop('id', None)
#     session.pop('username', None)
#     return redirect(url_for('admin'))

#---------APPLE---------
@app.route('/apple')
def apple():
    return render_template('apple.html')

@app.route('/applescab')
def applescab():
    return render_template('Apple_scab.html')

@app.route('/appleblackrot')
def appleblackrot():
    return render_template('Apple_Black_Rot.html')

@app.route('/cedarapplerust')
def cedarapplerust():
    return render_template('Cedar_Apple_Rust.html')

#---------TOMATO---------
@app.route('/tomato')
def tomato():
    return render_template('tomato.html')

@app.route('/tomato_bacterial_spot')
def tomato_bacterial_spot():
    return render_template('Tomato_Bacterial_Spot.html')

@app.route('/tomato_early_blight')
def tomato_early_blight():
    return render_template('Tomato_Early_Blight.html')

@app.route('/tomato_late_blight')
def tomato_late_blight():
    return render_template('tomato_late_blight.html')

@app.route('/tomato_leaf_mold')
def tomato_leaf_mold():
    return render_template('tomato_leaf_mold.html')

@app.route('/tomato_septoria_leaf_spot')
def tomato_septoria_leaf_spot():
    return render_template('Tomato_Septoria_Leaf_Spot.html')

@app.route('/tomato_spider_mites')
def tomato_spider_mites():
    return render_template('Tomato_Spider_Mites.html')

@app.route('/tomato_target_spot')
def tomato_target_spot():
    return render_template('tomato_target_spot.html')

@app.route('/tomato_mosaic_virus')
def tomato_mosaic_virus():
    return render_template('Tomato_Mosaic_Virus.html')

@app.route('/tomato_yellow_leaf_curl_virus')
def tomato_yellow_leaf_curl_virus():
    return render_template('Tomato_Yellow_Leaf_Curl_Virus.html')

#---------GRAPE---------
@app.route('/grape')
def grape():
    return render_template('grape.html')

@app.route('/grape_black_rot')
def grape_black_rot():
    return render_template('grape_black_rot.html')

@app.route('/grape_esca')
def grape_esca():
    return render_template('grape_esca.html')

@app.route('/grape_leaf_blight')
def grape_leaf_blight():
    return render_template('grape_leaf_blight.html')

#-----------cherry---------
@app.route('/cherry')
def cherry():
    return render_template('cherry.html')

@app.route('/cherry_powdery_mildew')
def cherrypowderymildew():
    return render_template('cherry_powdery_mildew.html')

#-------CORN-------------
@app.route('/corn')
def corn():
    return render_template('corn.html')

@app.route('/corn_grey_leaf_spot')
def corn_grey_leaf_spot():
    return render_template('corn_grey_leaf_spot.html')

@app.route('/corn_common_rust')
def corn_common_rust():
    return render_template('corn_common_rust.html')

@app.route('/corn_northern_leaf_blight')
def corn_northern_leaf_blight():
    return render_template('corn_northern_leaf_blight.html')

#---------STRAWBERRY---------
@app.route('/strawberry')
def strawberry():
    return render_template('strawberry.html')

@app.route('/strawberry_leaf_scorch')
def strawberry_leaf_scorch():
    return render_template('strawberry_leaf_scorch.html')

#---------POTATO---------
@app.route('/potato')
def potato():
    return render_template('potato.html')

@app.route('/potato-early_blight')
def potato_early_blight():
    return render_template('potato-early_blight.html')

@app.route('/potato-late_blight')
def potato_late_blight():
    return render_template('potato-late_blight.html')

#---------SOYBEAN---------
@app.route('/soybean')
def soybean():
    return render_template('soybean.html')

@app.route('/soybean_cercospora_leaf_blight')
def soybean_cercospora_leaf_blight():
    return render_template('Soybean_Cercospora_Leaf_Blight.html')

#---------PEPPER BELL---------
@app.route('/pepper-bell')
def pepperbell():
    return render_template('pepper-bell.html')

@app.route('/pepper-bell_bacterial_spot')
def pepperbell_bacterial_spot():
    return render_template('pepper-bell_bacterial_spot.html')

#---------PEACH---------
@app.route('/peach')
def peach():
    return render_template('peach.html')

@app.route('/peach_bacterial_spot')
def peach_bacterial_spot():
    return render_template('peach_bacterial_spot.html')

#---------SQUASH---------
@app.route('/squash')
def squash():
    return render_template('squash.html')

@app.route('/squash_powdery_mildew')
def squashpowderymildew():
    return render_template('squash_powdery_mildew.html')

#---------ORANGE---------
@app.route('/orange')
def orange():
    return render_template('orange.html')

@app.route('/Orange_Haunglongbing')
def Orange_Haunglongbing():
    return render_template('Orange_Haunglongbing(Citrus_greening).html')



if __name__ == "__main__":
    app.run(debug=True, port=8000)