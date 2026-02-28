from flask import Flask, render_template  # ← add render_template here
from database.db import init_db
from routes.auth_routes import auth_bp
from routes.pdf_routes import pdf_bp
from routes.quiz_routes import quiz_bp
from routes.curve_routes import curve_bp
from routes.profileroutes import profile_bp

import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")

    with app.app_context():
        init_db()

    # ✅ Landing page route — inside create_app
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
    app.run(debug=True)