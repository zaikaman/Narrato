from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..services.shov_api import shov_send_otp, shov_verify_otp

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        shov_send_otp(email)
        return redirect(url_for('auth.verify', email=email))
    return render_template('login.html')

@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    email = request.args.get('email')
    if request.method == 'POST':
        pin = request.form['pin']
        response = shov_verify_otp(email, pin)
        if response.get('success'):
            session['email'] = email
            return redirect(url_for('index'))
        else:
            flash("Invalid OTP. Please try again.")
            return redirect(url_for('auth.verify', email=email))
    return render_template('verify.html', email=email)

@auth_bp.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('index'))
