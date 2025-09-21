# Deployment Guide

This application is configured for deployment on platforms like Heroku and Vercel.

## Heroku

The `Procfile` is included for Heroku deployment:

```
web: gunicorn app:app
```

This command tells Heroku to serve the application using the `gunicorn` web server.

### Setup

1.  Create a Heroku app.
2.  Push the code to Heroku.
3.  In the Heroku dashboard, go to **Settings** > **Config Vars** and add all the environment variables listed in the [Environment Variables](./environment.md) documentation.

## Vercel

A `vercel.json` file is included for Vercel deployment. This file configures the serverless function for the Python backend.

```json
{
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app.py"
    }
  ]
}
```

### Setup

1.  Import the project into Vercel.
2.  In the Vercel project settings, go to **Environment Variables** and add all the required variables.
3.  Deploy the project.
