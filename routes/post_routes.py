from flask import Blueprint
from controllers.post_controller import generate_with_ai,generate_with_data, post_feedback, edit_post
from middleware import authentication_middleware

posts_api_routes = Blueprint("posts", __name__)

@posts_api_routes.route("/api/post/data",methods=["POST"])
@authentication_middleware
def post_generate_data_route():
    return generate_with_data()


@posts_api_routes.route("/api/post/ai",methods=["POST"])
@authentication_middleware
def post_generate_ai_route():
    return generate_with_ai()

@posts_api_routes.route("/api/post",methods=["POST"])
@authentication_middleware
def post_feedback_route():
    return post_feedback()

@posts_api_routes.route("/api/post",methods=["PATCH"])
@authentication_middleware
def edit_post_route():
    return edit_post()
