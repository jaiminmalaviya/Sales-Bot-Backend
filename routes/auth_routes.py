from flask import Blueprint
from controllers.auth_controller import user_create, user_login, user_update, user_delete, gmail_auth, oauth2callback, gmail_watch, gmail_notification, disconnect_gmail, send_gmail
from middleware import authentication_middleware


auth_api_routes = Blueprint("auth", __name__)


@auth_api_routes.route("/api/auth/login", methods=["POST"])
def auth_login_route():
    return user_login()


@auth_api_routes.route("/api/auth/signup", methods=["POST"])
@authentication_middleware
def auth_create_route():
    return user_create()


@auth_api_routes.route("/api/auth/update", methods=["PUT"])
@authentication_middleware
def auth_update_route():
    return user_update()


@auth_api_routes.route("/api/auth/delete", methods=["DELETE"])
@authentication_middleware
def auth_delete_route():
    return user_delete()


@auth_api_routes.route("/api/auth/gmail", methods=["GET"])
def auth_gmail_route():
    return gmail_auth()


@auth_api_routes.route("/oauth2callback", methods=["GET"])
def auth_oauth2callback():
    return oauth2callback()


@auth_api_routes.route("/api/gmail/watch/<email>", methods=["POST"])
def gmail_watch_route(email):
    return gmail_watch(email)


@auth_api_routes.route("/api/gmail/notification", methods=["POST"])
def gmail_notification_route():
    return gmail_notification()


@auth_api_routes.route("/api/gmail/disconnect", methods=["DELETE"])
@authentication_middleware
def disconnect_gmail_route():
    return disconnect_gmail()


@auth_api_routes.route("/api/gmail/send/<sender_email>", methods=["POST"])
@authentication_middleware
def send_gmail_route(sender_email):
    return send_gmail(sender_email)