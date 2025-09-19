# Narrato: The AI-Powered Multimedia Storyteller

<p align="center">
  <img src="./static/images/logo-text.png" alt="Narrato Logo" width="400"/>
</p>

<p align="center">
  <a href="https://narrato-9ab718a4ca8c.herokuapp.com/" target="_blank">
    <img src="https://img.shields.io/badge/Live-Demo-brightgreen?style=for-the-badge&logo=heroku" alt="Live Demo"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python" alt="Python Version"/>
  <img src="https://img.shields.io/badge/Framework-Flask-orange?style=for-the-badge&logo=flask" alt="Flask Framework"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License"/>
</p>

**Narrato** is a magical web application that brings your ideas to life by automatically generating, illustrating, and narrating complete stories from a single prompt. Using a powerful pipeline of generative AI models, it creates a rich, multi-sensory storytelling experience.

> **Note:** The live demo is hosted on a free Heroku instance and may be slow or unavailable at times.

## ✨ Features

-   **✍️ AI Story Generation:** Leverages Google's Gemini to write engaging and creative stories.
-   **🎨 AI-Powered Illustrations:** Generates beautiful, consistent images for each paragraph using Runware and a smart character analysis pipeline.
-   **🎤 AI-Powered Narration:** Converts the story text into high-quality audio narration with the Speechify API.
-   **🤖 Intelligent Consistency Pipeline:** A unique, multi-step AI process analyzes the story to create a "character database" and "style guide," ensuring visual consistency across all illustrations.
-   **🔐 User Authentication:** Secure, password-less login system using OTPs sent via email, powered by Shov.com.
-   **📚 Story Library:** Users can view their personal story history and browse public stories created by others.
-   **📤 PDF Export:** Export your favorite stories into a beautifully formatted PDF book, complete with illustrations.
-   **⚙️ Asynchronous Generation:** A robust background worker queue handles the intensive AI generation process, allowing users to leave the page and come back later.

## 🚀 How It Works: The AI Pipeline

Narrato's magic lies in its state-of-the-art AI pipeline that ensures a high-quality, consistent output.

1.  **Prompt -> Story:** You provide a prompt. **Google Gemini** writes a complete story with a title, paragraphs, and a moral.
2.  **Story -> Analysis:** The application uses **Gemini** again to read the generated story and create two crucial documents:
    *   **Character Database:** Detailed descriptions of every character's appearance, clothing, and expressions.
    *   **Art Style Guide:** A consistent guide for color palette, lighting, and overall artistic style.
3.  **Analysis -> Image Prompts:** With the story, character database, and style guide, **Gemini** crafts highly detailed, consistent prompts for the image generation AI for *every single paragraph*.
4.  **Prompts -> Images:** The prompts are sent to the **Runware API** to generate illustrations. The results are stored in **Cloudinary**.
5.  **Text -> Audio:** The story's title and paragraphs are sent to the **Speechify API** to generate audio narration, which is also stored in **Cloudinary**.
6.  **Assembly:** The final story—with text, images, and audio—is assembled and saved to the user's history using **Shov.com**.

## 🛠️ Getting Started: Local Installation

Follow these steps to run Narrato on your local machine.

### Prerequisites

-   Python 3.9+
-   Git
-   A web browser

### 1. Clone the Repository

First, clone the repository to your local machine.
```bash
git clone <your-repository-url>
cd autoaistory
```
*(Note: Replace `<your-repository-url>` with the actual URL of your Git repository)*

### 2. Install Dependencies

Install all the required Python packages using pip.
```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

You'll need to provide API keys for the various services used in the project.

1.  Make a copy of the example environment file:
    ```bash
    # On Windows
    copy .env.example .env

    # On macOS/Linux
    cp .env.example .env
    ```
2.  Open the newly created `.env` file and add your secret keys. The application is designed to use multiple keys for services like Google and Speechify to avoid rate limits; you can add them as `GOOGLE_API_KEY_1`, `GOOGLE_API_KEY_2`, etc.

    ```ini
    # Flask Secret Key for Session Management
    SECRET_KEY="a_very_strong_and_random_secret_key"

    # Shov.com Database
    SHOV_API_KEY="your_shov_api_key"
    SHOV_PROJECT="your_shov_project_name"

    # Google Gemini API Keys (add as many as you have)
    GOOGLE_API_KEY_1="your_google_gemini_api_key_1"
    GOOGLE_API_KEY_2="your_google_gemini_api_key_2"

    # Speechify API Keys (add as many as you have)
    SPEECHIFY_KEY_1="your_speechify_api_key_1"

    # Runware API for Image Generation
    RUNWARE_TOKEN="your_runware_api_token"

    # Cloudinary for Media Storage
    CLOUDINARY_CLOUD_NAME="your_cloudinary_cloud_name"
    CLOUDINARY_KEY="your_cloudinary_api_key"
    CLOUDINARY_SECRET="your_cloudinary_api_secret"

    # Worker Secret (a random string to secure the worker endpoint)
    WORKER_SECRET="a_secure_random_string_for_worker_auth"
    ```

### 4. Run the Application

Once the dependencies are installed and your environment variables are set, you can start the Flask development server.

```bash
python app.py
```

The application will be available at `http://127.0.0.1:8080`.

## 📄 License

This project is licensed under the MIT License.
