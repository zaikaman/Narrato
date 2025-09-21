from flask import Flask, render_template
from dotenv import load_dotenv
import os
import sys
import cloudinary

sys.path.append(os.path.join(os.path.dirname(__file__), 'speechify-api-sdk-python', 'src'))

load_dotenv()

app = Flask(__name__)

# Import and register blueprints
from auth_routes import auth_bp
app.register_blueprint(auth_bp)

from story_routes import story_bp
app.register_blueprint(story_bp)

from api_routes import api_bp
app.register_blueprint(api_bp)

from stream_routes import stream_bp
app.register_blueprint(stream_bp)

# Configuration
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")

cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key = os.getenv("CLOUDINARY_KEY"),
    api_secret = os.getenv("CLOUDINARY_SECRET")
)

print(f"SHOV_API_KEY: {os.getenv('SHOV_API_KEY')}")
print(f"SHOV_PROJECT: {os.getenv('SHOV_PROJECT')}")

# Main route
@app.route('/')
def index():
    return render_template('index.html', show_browse_button=True)

# Run the app
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)