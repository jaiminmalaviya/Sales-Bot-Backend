import os
from flask import Flask
from flask_cors import CORS, cross_origin
from dotenv import load_dotenv
from routes.client_routes import api_routes  
from routes.case_routes import case_api_routes
from routes.user_routes import user_api_routes
from routes.auth_routes import auth_api_routes
from routes.query_routes import query_api_routes
from routes.blog_routes import blog_api_routes
from routes.chat_routes import chat_api_routes
from routes.post_routes import posts_api_routes
from helpers.start_consumers import start_consumers
from helpers.initialize import initialize
load_dotenv()


initialize()  # Create Admin user if no user is present
start_consumers()


app = Flask(__name__)
CORS(app, resources={"*": {"origins": "*"}})
app.config['CORS_HEADERS'] = 'Content-Type'

# Register API routes
app.register_blueprint(api_routes)
app.register_blueprint(case_api_routes)
app.register_blueprint(query_api_routes)
app.register_blueprint(auth_api_routes)
app.register_blueprint(user_api_routes)
app.register_blueprint(chat_api_routes)
app.register_blueprint(blog_api_routes)
app.register_blueprint(posts_api_routes)

@app.route("/")
@cross_origin()
def hello_world():
    return "<h1>Hello there</h1>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.getenv("PORT"))
    