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

### Architecture Note

The application uses a **streaming architecture** to handle the long-running task of story generation. When a user starts a new story, the server holds the HTTP connection open and streams progress updates back to the client using Server-Sent Events (SSE).

This means **you do not need a separate worker process or dyno**. All work is done within the `web` process. It is crucial, however, to set a long timeout on the web server (as shown in the `Procfile` with `--timeout 3600`) to prevent the server from prematurely closing the connection during story generation.