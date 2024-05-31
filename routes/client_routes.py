from flask import Blueprint
from controllers.company_controller import \
    create_company, get_single_company, get_company_data, update_company, delete_company
from controllers.client_controller import add_contact, delete_single_url, add_pages, delete_page, scrape_apollo_pages, get_contact, delete_contact
from middleware import authentication_middleware

api_routes = Blueprint("api", __name__)


@api_routes.route("/api/client/company", methods=["GET"])
@authentication_middleware
def get_company_data_route():
    return get_company_data()


@api_routes.route("/api/client/company/<client_id>", methods=["GET"])
@authentication_middleware
def get_single_company_route(client_id):
    return get_single_company(client_id)


@api_routes.route("/api/client/company", methods=["POST"])
@authentication_middleware
def create_company_route():
    return create_company()


@api_routes.route("/api/client/company/<client_id>", methods=["PATCH"])
@authentication_middleware
def update_company_route(client_id):
    return update_company(client_id)


@api_routes.route("/api/client/company", methods=["DELETE"])
@authentication_middleware
def delete_company_route():
    return delete_company()


@api_routes.route("/api/client/scrape", methods=["POST"])
def scrape_apollo():
    return scrape_apollo_pages()


@api_routes.route("/api/client/company/page", methods=["PUT"])
@authentication_middleware
def add_pages_route():
    return add_pages()


@api_routes.route("/api/client/company/page/<account_id>", methods=["DELETE"])
@authentication_middleware
def delete_page_route(account_id):
    return delete_page(account_id)


@api_routes.route("/api/client/company/page", methods=["DELETE"])
@authentication_middleware
def delete_single_page_url_route():
    return delete_single_url()


@api_routes.route("/api/client/contact/add", methods=["POST"])
@authentication_middleware
def add_contact_route():
    return add_contact()


@api_routes.route("/api/client/contact/get", methods=["GET"])
@authentication_middleware
def get_contact_route():
    return get_contact()

@api_routes.route("/api/client/contact", methods=["DELETE"])
@authentication_middleware
def delete_contact_data():
    return delete_contact()
