from flask import Flask
import os
import cloudinary
from config import DevelopmentConfig

def create_app(config_class=DevelopmentConfig):
    """Creates and configures the Flask application."""
    app = Flask(__name__, instance_relative_config=True, template_folder='../templates')

    app.config.from_object(config_class)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # --- Configuration ---
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_KEY"),
        api_secret=os.getenv("CLOUDINARY_SECRET")
    )

    # --- Register Blueprints ---
    from .routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from .routes.story import story_bp
    app.register_blueprint(story_bp)

    from .routes.api import api_bp
    app.register_blueprint(api_bp)

    from .routes.stream import stream_bp
    app.register_blueprint(stream_bp)

    # --- Main Route ---
    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html', show_browse_button=True)

    return app
