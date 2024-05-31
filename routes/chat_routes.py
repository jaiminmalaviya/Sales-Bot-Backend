from flask import Blueprint
from controllers.chat_controller import send_message, get_chat, start_chat, rate_message, get_chats, edit_message
from controllers.linkedin_controller import lin_add_message, lin_gen_message, lin_get_url,lin_save_url
from middleware import authentication_middleware
chat_api_routes = Blueprint("chat", __name__)


@chat_api_routes.route("/api/chat/<chat_id>", methods=["POST"])
@authentication_middleware
def send_msg(chat_id):
    return send_message(chat_id)


@chat_api_routes.route("/api/chat/<chat_id>", methods=["GET"])
@authentication_middleware
def get_msg(chat_id):
    return get_chat(chat_id)


@chat_api_routes.route("/api/chat", methods=["POST"])
@authentication_middleware
def start_cht():
    return start_chat()


@chat_api_routes.route("/api/chat/<message_id>/rate", methods=["POST"])
@authentication_middleware
def rate_msg(message_id):
    return rate_message(message_id)


@chat_api_routes.route("/api/chat/<message_id>", methods=["PATCH"])
@authentication_middleware
def update_msg(message_id):
    return edit_message(message_id)


@chat_api_routes.route("/api/chat/list", methods=["GET"])
@authentication_middleware
def get_all_chats():
    return get_chats()


@chat_api_routes.route("/api/chat/add/lin",methods=["POST"])
@authentication_middleware
def linkedin_save_route():
    return lin_add_message()


@chat_api_routes.route("/api/chat/gen/lin",methods=["POST"])
@authentication_middleware
def linkedin_message_route():
    return lin_gen_message()


@chat_api_routes.route("/api/chat/save/lin",methods=["POST"])
def linkedin_save_url_route():
    return lin_save_url()


@chat_api_routes.route("/api/chat/get/lin",methods=["POST"])
def linkedin_get_url_route():
    return lin_get_url()