from functools import wraps
from flask import session, redirect, url_for, request

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'email' not in session:
            return redirect(url_for('routes.auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
