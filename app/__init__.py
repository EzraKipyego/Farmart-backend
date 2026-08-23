from flask import Flask, jsonify
from config import Config
from app.extensions import db, jwt, cors


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    from app.auth import auth_bp
    from app.animals import animals_bp
    from app.orders import orders_bp
    from app.payments import payments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(animals_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(payments_bp)

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok", "service": "farmart-backend"}), 200

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"message": "Resource not found"}), 404

    @app.errorhandler(500)
    def server_error(error):
        app.logger.error(f"Internal server error: {error}")
        return jsonify({"message": "Internal server error"}), 500

    return app