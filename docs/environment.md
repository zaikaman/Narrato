# Environment Variables

The project requires several environment variables to be set for it to function correctly. These variables include API keys for various services and configuration settings.

Create a `.env` file in the root of the project and add the following variables:

```
# Google Gemini API Keys (for story generation)
# You can provide multiple keys. The application will rotate through them.
GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY_1"
GOOGLE_API_KEY_2="YOUR_GOOGLE_API_KEY_2"
# ... and so on

# Shov.com API Key (for database and OTP)
SHOV_API_KEY="YOUR_SHOV_API_KEY"
SHOV_PROJECT="YOUR_SHOV_PROJECT_NAME"

# Cloudinary Configuration (for image and audio storage)
CLOUDINARY_KEY="YOUR_CLOUDINARY_KEY"
CLOUDINARY_SECRET="YOUR_CLOUDINARY_SECRET"
CLOUDINARY_CLOUD_NAME="YOUR_CLOUDINARY_CLOUD_NAME"

# Speechify API Key (for audio narration)
SPEECHIFY_KEY="YOUR_SPEECHIFY_KEY"

# Hugging Face API Tokens (for image generation)
# You can provide multiple tokens. The application will rotate through them.
HUGGING_FACE_TOKEN="YOUR_HUGGING_FACE_TOKEN_1"
HUGGING_FACE_TOKEN_2="YOUR_HUGGING_FACE_TOKEN_2"
# ... and so on

# Secret key for signing worker requests
WORKER_SECRET="A_STRONG_RANDOM_SECRET_KEY"

# Flask Secret Key (for session management)
SECRET_KEY="A_DIFFERENT_STRONG_RANDOM_SECRET_KEY"
```

### Notes:

- **Multiple API Keys**: For services like Google Gemini and Hugging Face, you can provide multiple keys (`GOOGLE_API_KEY_2`, `HUGGING_FACE_TOKEN_2`, etc.). The application is designed to rotate through these keys, which can help manage rate limits.
- **`WORKER_SECRET`**: This is a secret key you create. It is used to authenticate requests to the background worker endpoint (`/api/run-worker`).
- **`SECRET_KEY`**: This is a standard Flask secret key used for signing session cookies. Make sure it is a long, random, and secret string.
