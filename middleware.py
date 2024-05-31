import functools
from flask import request, jsonify
import jwt
import os

def authentication_middleware(next):
    @functools.wraps(next)
    def decorated(*args, **kwargs):
        # Check for the 'Authorization' header
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"message": "Authorization Token missing or invalid"}), 401

        token = auth_header.split("Bearer ")[1]

        try:
            # Decode the token using the secret key
            decoded_token = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])

            # Extract user_id from the decoded token
            user_id = decoded_token.get("_id")
            
            if user_id is None:
                return jsonify({"message": "User ID not present in token"}), 401

            # Attach user_id to request for use in the route
            request.user_id = user_id
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401

        # Call the next middleware or route handler
        return next(*args, **kwargs)

    return decorated