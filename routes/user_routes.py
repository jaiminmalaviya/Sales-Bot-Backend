from flask import Blueprint
from controllers.auth_controller import get_users, get_user
from middleware import authentication_middleware

user_api_routes = Blueprint("user", __name__)

@user_api_routes.route("/api/user/list")
@authentication_middleware
def get_users_list():
    return get_users()


@user_api_routes.route("/api/user/<email>")
@authentication_middleware
def get_user_details(email):
    return get_user(email)