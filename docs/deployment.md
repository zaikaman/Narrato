# Deployment Guide

This application is configured for deployment on platforms like Heroku and Vercel.

## Heroku

The `Procfile` is included for Heroku deployment:

```
web: gunicorn run:app --timeout 3600
```

This command tells Heroku to serve the application using the `gunicorn` web server.

### Setup

1.  Create a Heroku app.
2.  Push the code to Heroku.
3.  In the Heroku dashboard, go to **Settings** > **Config Vars** and add all the environment variables listed in the [Environment Variables](./environment.md) documentation.