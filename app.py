import os
from flask import Flask, render_template
from database.db import init_db
from routes.auth_routes import auth_bp
from routes.pdf_routes import pdf_bp
from routes.quiz_routes import quiz_bp
from routes.curve_routes import curve_bp
from routes.profileroutes import profile_bp
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")

    with app.app_context():
        init_db()

    @app.route('/')
    def index():
        return render_template('start.html')

    app.register_blueprint(auth_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(curve_bp)
    app.register_blueprint(profile_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


