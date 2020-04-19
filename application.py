import os, sys
import hashlib, binascii

from flask import Flask, abort, jsonify, session, render_template, request, redirect, url_for
from flask_session import Session
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

"""---------------------------------------------------------------------------------------------------
                Login and registration methods
---------------------------------------------------------------------------------------------------"""

@app.route("/")
def index():
    #Check if the user is logged in and if so redirect them
    if logged_in():
        return redirect(url_for('home', username = session['user']))
    return render_template("index.html");

@app.route("/login", methods=["POST"])
def login():
    """ Attempt to log a user in """

    # Get the form information
    username = request.form.get("username")
    password = request.form.get("password")

    # Make sure the user exists
    if db.execute("SELECT * FROM accounts WHERE username = :username", {"username": username}).rowcount == 0:
        return render_template("index.html", message="user")
    else:
        #the user exists so get their password
        temp = db.execute("SELECT password FROM accounts WHERE username = :username", {"username": username}).fetchone()
        #compare password entered with password stored
        if(verify_password(temp[0], password)):
            # set the session_id
            if 'user' not in session:
                session['user'] = username;
                print(session['user'])
            elif 'user' in session and session['user'] == None:
                session['user'] = username;
                init_data()
            #Loads the homepage with the proper URL and displays the users name     
            return redirect(url_for('home'))
        else:
            #Passwords dont match so reload the login page
            return render_template("index.html", message = "pass")

@app.route("/register", methods=["POST", "GET"])
def register():
    #The user is already logged in so redirect them
    if logged_in():
        return redirect(url_for('home', username = session['user']))
    #if we want to register then serve the registration page
    if request.method == 'GET':
        return render_template("registration.html")
    # Get the form information
    username = request.form.get("username")
    password = request.form.get("password")
    email = request.form.get("email")

    # make sure the user doesnt exist
    if db.execute("SELECT * FROM accounts WHERE username = :username", {"username": username}).rowcount == 0:
        # Hash the password for storage
        pword = hash_password(password)
        # Register the user
        try:
            db.execute("INSERT INTO accounts (username, password, email) VALUES (:username, :password, :email)",
                       {"username": username, "password": pword, "email": email})
            db.commit()
            return render_template("index.html")
        except exc.IntegrityError:
            return render_template("error.html", message = "Failed to register user")
    else:
        return render_template("index.html")

@app.route("/logout", methods=["GET"])
def logout():
    if logged_in():
        session['user'] = None
        session['data'].clear()
    return redirect(url_for('index'))

"""---------------------------------------------------------------------------------------------------
                Registered user methods
---------------------------------------------------------------------------------------------------"""

@app.route("/home", methods = ["GET"])
def home():
    if not logged_in():
        return redirect(url_for('index'))
    #return render_template("home.html", username = session['user'])
    return render_template("home.html", data = session['data'])

@app.route("/search", methods = ["POST", "GET"])
def search():
    if not logged_in():
        return redirect(url_for('index'))
    if request.method =='GET':
        return render_template("search.html")
    isbn = request.form.get("ISBN")
    author = request.form.get("author")
    title = request.form.get("title")
    books = user_query(isbn, author, title)
    return render_template("results.html", data = books)

@app.route("/results", methods = ["POST"])
def results(data):
    if not logged_in():
        return redirect(url_for('index'))
    return render_template("results.html", data = data)

@app.route("/results/book/<book_id>", methods = ['POST', 'GET'])
def book(book_id):
    if not logged_in():
        return redirect(url_for('index'))
    book = db.execute("SELECT ISBN, title, author, publish_date, id FROM books WHERE id = :id", {"id": book_id}).fetchone();
    review = user_review(session['data']['id'], book_id)
    reviews = book_reviews(book_id)
    stats = statistics(book_id)
    if request.method == 'POST' and not review:
        rating_text = request.form.get("textarea_1")
        rating = request.form.get("rating")
        db.execute("INSERT INTO review (user_id, book_id, book_score, book_review) VALUES (:u_id, :b_id, :score, :review)",
                   {"u_id": session['data']['id'], "b_id": book_id,"score": rating, "review": rating_text})
        db.commit()
    return render_template("book.html", book = book, review = review, reviews = reviews, stats = stats)

"""---------------------------------------------------------------------------------------------------
                API
---------------------------------------------------------------------------------------------------"""

@app.route("/api/<isbn>", methods = ["GET"])
def isbn_api(isbn):
    """Return the details about a book"""
    book = db.execute("SELECT * FROM books WHERE ISBN = :isbn", {"isbn": isbn}).fetchone()
    if book == None:
        #return jsonify({"error": "Invalid ISBN"}), 422
        abort(404, description="ISBN not found")
    average = db.execute("SELECT AVG(book_score) FROM review WHERE book_id = :id", {"id": book['id']}).scalar();
    count = db.execute("SELECT COUNT(*) FROM review WHERE book_id = :id", {"id": book['id']}).scalar();
    nums = dict(count = count, average = float(str(average)))
    return jsonify({
        "id": book["id"],
        "isbn": book['isbn'],
        "title": book['title'],
        "author": book['author'],
        "year": book['publish_date'],
        "review_count": nums["count"],
        "average_score": nums["average"]
    })

"""---------------------------------------------------------------------------------------------------
                Non-Route methods
---------------------------------------------------------------------------------------------------"""

# Hashing code taken from:
# https://www.vitoshacademy.com/hashing-passwords-in-python/
def hash_password(password):
    """Hash a password for storing."""
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), 
                                salt, 100000)
    pwdhash = binascii.hexlify(pwdhash)
    return (salt + pwdhash).decode('ascii')

def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    salt = stored_password[:64]
    stored_password = stored_password[64:]
    pwdhash = hashlib.pbkdf2_hmac('sha512', 
                                  provided_password.encode('utf-8'), 
                                  salt.encode('ascii'), 
                                  100000)
    pwdhash = binascii.hexlify(pwdhash).decode('ascii')
    return pwdhash == stored_password

def logged_in():
    if 'user' in session:
           if session['user'] != None:
               return True
    return False

# Put user data into the session variable
def init_data():
    temp = db.execute("SELECT username, email, id FROM accounts WHERE username = :username", {"username": session['user']}).fetchone()
    count = db.execute("SELECT count(*) FROM review WHERE user_id = :id", {"id":temp['id']}).scalar()
    data = dict(temp)
    data['count'] = count
    session['data'] = data

# NOT USED
def update_data():
    count = db.execute("SELECT count(*) FROM review WHERE user_id = :id", {"id":temp['id']}).scalar()
    session['data']['count'] = count

# Runs a search for a user
def user_query(isbn, author, title):
    if isbn and author and title:
        return db.execute("SELECT ISBN, title, author, publish_date, id FROM books WHERE isbn ILIKE :isbn AND author ILIKE :author AND title ILIKE :title",
                          {"isbn": "%" + isbn + "%", "author": "%" + author + "%", "title": "%" + title + "%"}).fetchall()
    if isbn and author:
        return db.execute("SELECT ISBN, title, author, publish_date, id FROM books WHERE isbn ILIKE :isbn AND author ILIKE :author",
                          {"isbn": "%" + isbn + "%", "author": "%" + author + "%"}).fetchall()
    if author and title:
        return db.execute("SELECT ISBN, title, author, publish_date, id FROM books WHERE author ILIKE :author AND title ILIKE :title",
                       {"author": "%" + author + "%", "title": "%" + title + "%"}).fetchall()
    if isbn and title:
        return db.execute("SELECT ISBN, title, author, publish_date, id FROM books WHERE isbn ILIKE :isbn AND title ILIKE :title",
                       {"isbn": "%" + isbn + "%", "item": "%" + author + "%", "title": "%" + title + "%"}).fetchall()
    if isbn:
        return db.execute("SELECT ISBN, title, author, publish_date, id FROM books WHERE isbn ILIKE :isbn", {"isbn": "%" + isbn + "%"}).fetchall()
    if author:
        return db.execute("SELECT ISBN, title, author, publish_date, id FROM books WHERE author ILIKE :author", {"author": "%" + author + "%"}).fetchall()
    if title:
        return db.execute("SELECT ISBN, title, author, publish_date, id FROM books WHERE title ILIKE :title", {"title": "%" + title + "%"}).fetchall()

# gives me the users reviews of a particular book
def user_review(user_id, book_id):
    return db.execute("SELECT book_score, book_review FROM review WHERE book_id = :book_id AND user_id = :user_id", {"book_id": book_id, "user_id": user_id}).fetchall()

# gives me all reviews for a particular book with a username
def book_reviews(book_id):
    return db.execute("SELECT A.username, R.book_score, R.book_review FROM review R, accounts A WHERE R.book_id = :book_id AND R.user_id = A.id", {"book_id": book_id}).fetchall()

# give user review count
def review_count():
    return db.execute("SELECT count(*) FROM review WHERE user_id = :id", {"id":session['data']['username']}).scalar()

def statistics(book_id):
    scores= db.execute("SELECT book_score FROM review WHERE book_id = :book_id", {"book_id": book_id}).fetchall()
    count = 0;
    total = 0;
    for score in scores:
        total = score['book_score'] + total
        count+=1
    if count > 0:
        avg = total/count
    else:
        avg = 0
#    count = db.execute("SELECT count(*) FROM review WHERE book_id = :book_id", {"book_id":book_id}).scalar()
    return {"average":avg, "count": count}

"""---------------------------------------------------------------------------------------------------
                Error Handling
---------------------------------------------------------------------------------------------------"""

@app.errorhandler(404)
def resource_not_found(e):
    #Page not found.
    return jsonify(error=str(e)), 404
