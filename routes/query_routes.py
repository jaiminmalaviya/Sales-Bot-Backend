from flask import Blueprint
from controllers.query_controller import handle_query, handle_question, add_industry_controller, \
    icebreaker, get_icebreakers, rate_icebreaker, update_icebreaker, delete_icebreaker
from middleware import authentication_middleware

query_api_routes = Blueprint("query", __name__)


@query_api_routes.route("/api/query/docs", methods=["POST"])
@authentication_middleware
def get_query_doc_route():
    return handle_query()


@query_api_routes.route("/api/query/ask", methods=["POST"])
@authentication_middleware
def get_query_answer_route():
    return handle_question()


@query_api_routes.route("/api/query/addIndustry", methods=["POST"])
@authentication_middleware
def add_industry_route():
    return add_industry_controller()


@query_api_routes.route("/api/query/icebreaker", methods=["POST"])
@authentication_middleware
def generate_icebreaker():
    return icebreaker()


@query_api_routes.route("/api/query/icebreaker", methods=["GET"])
@authentication_middleware
def get_all_ibs():
    return get_icebreakers()


@query_api_routes.route("/api/query/icebreaker/feedback", methods=["POST"])
@authentication_middleware
def rate_ib():
    return rate_icebreaker()

@query_api_routes.route("/api/query/icebreaker", methods=["PATCH"])
@authentication_middleware
def update_ib():
    return update_icebreaker()

@query_api_routes.route("/api/query/icebreaker/<iceBreaker_id>", methods=["DELETE"])
@authentication_middleware
def delete_ib(iceBreaker_id):
    return delete_icebreaker(iceBreaker_id)
