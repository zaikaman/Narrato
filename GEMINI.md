# Gemini AI Agent Context

This document outlines the context and operating instructions for the Gemini AI agent working on this project.

## Primary Instructions

1.  **Language:** Always respond to the user in Vietnamese.
2.  **Content and Code:** All generated code, file content, and commit messages must be in English.

## Project Overview: autoaistory

`autoaistory` is a Flask-based web application designed to automatically generate, illustrate, and narrate stories.

### Core Functionality

*   **Story Generation:** Uses the Google Gemini API (`google-generativeai`) to create stories based on user-provided prompts.
*   **Image Generation:** Leverages the Runware API for image creation and Cloudinary for storing the generated illustrations for each paragraph of the story.
*   **Audio Narration:** Integrates the Speechify API (`speechify-api-sdk-python`) to convert story text into audio narration.
*   **Data Persistence:** Utilizes `shov.com` as a key-value database service to store user data, story content, and generation tasks.
*   **User Authentication:** Implements an OTP-based login system (via `shov.com`) allowing users to manage their created stories.
*   **Story Management:** Users can view their story history and delete stories.
*   **Export:** Provides functionality to export stories into PDF format using `xhtml2pdf`.

### Technical Stack

*   **Backend:** Python with Flask
*   **AI Services:** Google Gemini, Runware, Speechify
*   **Database:** Shov.com (Key-Value Store)
*   **Cloud Storage:** Cloudinary
*   **Frontend:** Standard HTML, CSS, JavaScript with templates managed by Flask.
*   **Deployment:** Configured for services like Heroku or Vercel (`Procfile`, `vercel.json`).

Also, do not try to run flask or app.py commands, the user wants to run the app by themselves.