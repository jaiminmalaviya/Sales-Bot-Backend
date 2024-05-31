from flask import Blueprint
from controllers.case_controller import create_case,case_data,delete_case
from middleware import authentication_middleware

case_api_routes = Blueprint("case", __name__)

@case_api_routes.route("/api/case/get-case")
@authentication_middleware
def get_case_data_route():
    return case_data()

@case_api_routes.route("/api/case/create", methods=["POST"])
@authentication_middleware
def create_case_route():
    return create_case()

@case_api_routes.route("/api/case/delete", methods=["DELETE"])
@authentication_middleware
def delete_case_route():
    return delete_case()
