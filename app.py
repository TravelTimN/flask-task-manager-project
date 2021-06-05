import os
from functools import wraps
from flask import (
    Flask, flash, render_template,
    redirect, request, session, url_for)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


# @login_required decorator
# https://flask.palletsprojects.com/en/2.0.x/patterns/viewdecorators/#login-required-decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # no "user" in session
        if "user" not in session:
            flash("You must log in to view this page")
            return redirect(url_for("login"))
        # user is in session
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
@app.route("/get_tasks")
def get_tasks():
    # find all tasks
    tasks = list(mongo.db.tasks.find())
    return render_template("tasks.html", tasks=tasks)


@app.route("/search", methods=["GET", "POST"])
def search():
    # find only the tasks the user has queried
    query = request.form.get("query")
    tasks = list(mongo.db.tasks.find({"$text": {"$search": query}}))
    return render_template("tasks.html", tasks=tasks)


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" not in session:
        # only if there isn't a current session["user"]
        if request.method == "POST":
            # check if username already exists in db
            existing_user = mongo.db.users.find_one(
                {"username": request.form.get("username").lower()})

            if existing_user:
                flash("Username already exists")
                return redirect(url_for("register"))

            register = {
                "username": request.form.get("username").lower(),
                "password": generate_password_hash(request.form.get("password"))
            }
            mongo.db.users.insert_one(register)

            # put the new user into 'session' cookie
            session["user"] = request.form.get("username").lower()
            flash("Registration Successful!")
            return redirect(url_for("profile", username=session["user"]))

        return render_template("register.html")

    # user is already logged-in, direct them to their profile
    return redirect(url_for("profile", username=session["user"]))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" not in session:
        # only if there isn't a current session["user"]
        if request.method == "POST":
            # check if username exists in db
            existing_user = mongo.db.users.find_one(
                {"username": request.form.get("username").lower()})

            if existing_user:
                # ensure hashed password matches user input
                if check_password_hash(
                        existing_user["password"], request.form.get("password")):
                            session["user"] = request.form.get("username").lower()
                            flash("Welcome, {}".format(
                                request.form.get("username")))
                            return redirect(url_for(
                                "profile", username=session["user"]))
                else:
                    # invalid password match
                    flash("Incorrect Username and/or Password")
                    return redirect(url_for("login"))

            else:
                # username doesn't exist
                flash("Incorrect Username and/or Password")
                return redirect(url_for("login"))

        return render_template("login.html")

    # user is already logged-in, direct them to their profile
    return redirect(url_for("profile", username=session["user"]))


@app.route("/profile/<username>", methods=["GET", "POST"])
@login_required
def profile(username):
    # grab only the session["user"] profile
    if session["user"].lower() == username.lower():
        # find the session["user"] record
        user = mongo.db.users.find_one({"username": username})
        # grab only the tasks by this session["user"]
        tasks = list(mongo.db.tasks.find({"created_by": username}))
        return render_template("profile.html", user=user, tasks=tasks)

    # take the incorrect user to their own profile
    return redirect(url_for("profile", username=session["user"]))


@app.route("/logout")
@login_required
def logout():
    # remove user from session cookies
    flash("You have been logged out")
    session.pop("user")
    return redirect(url_for("login"))


@app.route("/add_task", methods=["GET", "POST"])
@login_required
def add_task():
    # adding a new task
    if request.method == "POST":
        is_urgent = "on" if request.form.get("is_urgent") else "off"
        task = {
            "category_name": request.form.get("category_name"),
            "task_name": request.form.get("task_name"),
            "task_description": request.form.get("task_description"),
            "is_urgent": is_urgent,
            "due_date": request.form.get("due_date"),
            "created_by": session["user"]
        }
        mongo.db.tasks.insert_one(task)
        flash("Task Successfully Added")
        return redirect(url_for("get_tasks"))

    # generate the form for new tasks
    categories = mongo.db.categories.find().sort("category_name", 1)
    return render_template("add_task.html", categories=categories)


@app.route("/edit_task/<task_id>", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    # find the task
    task = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})
    if session["user"].lower() == task["created_by"].lower():
        # the session["user"] must be the user who created this task
        if request.method == "POST":
            is_urgent = "on" if request.form.get("is_urgent") else "off"
            submit = {
                "category_name": request.form.get("category_name"),
                "task_name": request.form.get("task_name"),
                "task_description": request.form.get("task_description"),
                "is_urgent": is_urgent,
                "due_date": request.form.get("due_date"),
                "created_by": session["user"]
            }
            mongo.db.tasks.update({"_id": ObjectId(task_id)}, submit)
            flash("Task Successfully Updated")

        categories = mongo.db.categories.find().sort("category_name", 1)
        return render_template("edit_task.html", task=task, categories=categories)

    # not the correct user to edit this task
    flash("You don't have access to edit this task")
    return redirect(url_for("get_tasks"))


@app.route("/delete_task/<task_id>")
@login_required
def delete_task(task_id):
    # find the task
    task = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})
    if session["user"].lower() == task["created_by"].lower():
        # the session["user"] must be the user who created this task
        mongo.db.tasks.remove({"_id": ObjectId(task_id)})
        flash("Task Successfully Deleted")
        return redirect(url_for("get_tasks"))

    # not the correct user to delete this task
    flash("You don't have access to delete this task")
    return redirect(url_for("get_tasks"))


@app.route("/get_categories")
@login_required
def get_categories():
    # admin-only page
    if session["user"] == "admin":
        categories = list(mongo.db.categories.find().sort("category_name", 1))
        return render_template("categories.html", categories=categories)

    # user is not admin
    flash("You do not have acess to this page!")
    return redirect(url_for("get_tasks"))


@app.route("/add_category", methods=["GET", "POST"])
@login_required
def add_category():
    # admin-only page
    if session["user"] == "admin":
        # add a new category
        if request.method == "POST":
            category = {
                "category_name": request.form.get("category_name")
            }
            mongo.db.categories.insert_one(category)
            flash("New Category Added")
            return redirect(url_for("get_categories"))

        # generate the form to add a new category
        return render_template("add_category.html")

    # user is not admin
    flash("You do not have acess to this page!")
    return redirect(url_for("get_tasks"))


@app.route("/edit_category/<category_id>", methods=["GET", "POST"])
@login_required
def edit_category(category_id):
    # admin-only page
    if session["user"] == "admin":
        # update the category
        if request.method == "POST":
            submit = {
                "category_name": request.form.get("category_name")
            }
            mongo.db.categories.update({"_id": ObjectId(category_id)}, submit)
            flash("Category Successfully Updated")
            return redirect(url_for("get_categories"))

        # generate the form to update the category
        category = mongo.db.categories.find_one({"_id": ObjectId(category_id)})
        return render_template("edit_category.html", category=category)

    # user is not admin
    flash("You do not have acess to this page!")
    return redirect(url_for("get_tasks"))


@app.route("/delete_category/<category_id>")
@login_required
def delete_category(category_id):
    # admin-only page
    if session["user"] == "admin":
        # update the category
        mongo.db.categories.remove({"_id": ObjectId(category_id)})
        flash("Category Successfully Deleted")
        return redirect(url_for("get_categories"))

    # user is not admin
    flash("You do not have acess to this page!")
    return redirect(url_for("get_tasks"))


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
