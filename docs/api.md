# API Reference

This document provides a reference for the API endpoints available in the Auto-AI-Story application.

## Authentication API (`auth_routes.py`)

- **`/login`**
  - **Methods**: `GET`, `POST`
  - **Description**: `GET` displays the login page. `POST` takes an email address and sends an OTP.

- **`/verify`**
  - **Methods**: `GET`, `POST`
  - **Description**: `GET` displays the OTP verification page. `POST` verifies the OTP and logs the user in.

- **`/logout`**
  - **Methods**: `GET`
  - **Description**: Logs the user out.

## Story API (`story_routes.py`)

- **`/browse`**
  - **Methods**: `GET`
  - **Description**: Displays all public stories.

- **`/stories/<title>`**
  - **Methods**: `GET`
  - **Description**: Displays a specific story by its title.

- **`/view_story/<story_uuid>`**
  - **Methods**: `GET`
  - **Description**: Displays a specific story by its UUID.

- **`/history`**
  - **Methods**: `GET`
  - **Description**: Displays the story history for the logged-in user. Requires login.

- **`/delete_story`**
  - **Methods**: `POST`
  - **Description**: Deletes a story. Requires login and ownership.

- **`/export_pdf/<story_uuid>`**
  - **Methods**: `GET`
  - **Description**: Exports a story as a PDF file.

## Story Generation API (`stream_routes.py`)

This is the primary API for creating stories.

- **`/generate_story_stream`**
  - **Methods**: `GET`
  - **Description**: Starts a story generation process based on URL parameters (`prompt`, `imageMode`, etc.). The server holds the connection open and streams progress updates back to the client using Server-Sent Events (SSE).
