from flask import Blueprint
from controllers.blog_controller import fetch_blog
from middleware import authentication_middleware


blog_api_routes = Blueprint("blog", __name__)


@blog_api_routes.route("/api/blog", methods=["POST"])
def fetch_blog_route():
    return fetch_blog()

