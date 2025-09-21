# Installation Guide

This guide will walk you through the steps to set up and run the Auto-AI-Story project on your local machine.

## 1. Prerequisites

- Python 3.13.0
- `pip` for package management

## 2. Clone the Repository

First, clone the project repository to your local machine:

```bash
git clone <repository-url>
cd autoaistory
```

## 3. Set Up a Virtual Environment

It is highly recommended to use a virtual environment to manage project dependencies.

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows
.\venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

## 4. Install Dependencies

Install all the required Python packages using pip and the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

## 5. Configure Environment Variables

Create a `.env` file in the root of the project by copying the `.env.example` file. Then, fill in the required API keys and configuration values.

See the [Environment Variables](./environment.md) documentation for more details on each variable.

## 6. Run the Application

Once the dependencies are installed and the environment variables are set, you can run the Flask development server:

```bash
python run.py
```

The application will be available at `http://127.0.0.1:8080`.
