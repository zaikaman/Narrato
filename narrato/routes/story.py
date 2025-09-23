from flask import Blueprint, render_template, request, jsonify, send_file, Response
from urllib.parse import unquote
import os
import copy
from xhtml2pdf import pisa
from io import BytesIO
import requests
import base64
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from ..services.shov_api import shov_where, shov_remove, shov_contents
from ..core.decorators import login_required

story_bp = Blueprint('story', __name__)

@story_bp.route('/audio/<path:filename>')
def serve_audio(filename):
    try:
        return send_file(filename, mimetype='audio/mpeg')
    except Exception as e:
        print(f"Error serving audio file: {str(e)}")
        return jsonify({"error": "Could not play audio file"}), 404

@story_bp.route('/stories')
def list_stories():
    """List all stories in the database"""
    return jsonify(shov_contents())

@story_bp.route('/browse')
def browse_stories():
    """Browse all public stories"""
    stories_response = shov_where('stories', {'public': True})
    public_stories = stories_response.get('items', [])
    return render_template('browse.html', stories=public_stories, show_browse_button=False)


@story_bp.route('/stories/<title>')
def get_story(title):
    """Get a story from the database"""
    decoded_title = unquote(title)
    story_response = shov_where('stories', {'title': decoded_title})
    if not story_response.get('success', True):
        return render_template('story_view.html', story=None, error="database_down"), 503

    stories = story_response.get('items', [])
    if stories:
        story = stories[0]['value']
        return render_template('story_view.html', story=story)
    
    return render_template('story_view.html', story=None, error="not_found"), 404


@story_bp.route('/view_story/<story_uuid>')
def view_story(story_uuid):
    """Get a story from the database by ID"""
    story_response = shov_where('stories', {'story_uuid': story_uuid})
    
    if not story_response.get('success', True):
        return render_template('story_view.html', story=None, error="database_down"), 503

    stories = story_response.get('items', [])
    if stories:
        story = stories[0]['value']
        return render_template('story_view.html', story=story)
    
    return render_template('story_view.html', story=None, error="not_found"), 404

@story_bp.route('/history')
@login_required
def story_history():
    """Display user's story history"""
    from flask import session
    stories_response = shov_where('stories', {'email': session['email']})
    user_stories = stories_response.get('items', [])
    return render_template('history.html', stories=user_stories)

@story_bp.route('/delete_story', methods=['POST'])
@login_required
def delete_story():
    """Delete a story."""
    from flask import session
    data = request.get_json()
    story_id = data.get('story_id')

    if not story_id:
        return jsonify({"success": False, "error": "Invalid request: No story ID provided."} ), 400

    stories_response = shov_where('stories', {'email': session['email']})
    user_stories = stories_response.get('items', [])
    owned_story_ids = [story['id'] for story in user_stories]

    if story_id in owned_story_ids:
        delete_response = shov_remove('stories', story_id)
        if delete_response.get('success'):
            return jsonify({"success": True})
        else:
            error_msg = delete_response.get('error', 'Unknown error during deletion.')
            return jsonify({"success": False, "error": error_msg}), 500
    else:
        return jsonify({"success": False, "error": "You are not authorized to delete this story."} ), 403

@story_bp.route('/export_pdf/<story_uuid>')
def export_pdf(story_uuid):
    """Export a story as a PDF"""
    story_response = shov_where('stories', {'story_uuid': story_uuid})
    stories = story_response.get('items', [])
    if stories:
        story = stories[0]['value']
        story = copy.deepcopy(story)

        static_path = os.path.join(os.path.dirname(__file__), '..' ,'static')
        medieval_font_path = os.path.join(static_path, 'MedievalSharp', 'MedievalSharp-Regular.ttf')
        literata_font_path = os.path.join(static_path, 'Literata', 'Literata-VariableFont_opsz,wght.ttf')
        
        if os.path.exists(medieval_font_path):
            pdfmetrics.registerFont(TTFont('MedievalSharp', medieval_font_path))
        if os.path.exists(literata_font_path):
            pdfmetrics.registerFont(TTFont('Literata', literata_font_path))

        if 'images' in story:
            new_images = []
            for image_data in story['images']:
                new_image_data = image_data.copy()
                if new_image_data.get('url') and new_image_data['url'].startswith('http'):
                    try:
                        response = requests.get(new_image_data['url'], timeout=10)
                        response.raise_for_status()
                        content_type = response.headers.get('Content-Type', 'image/jpeg')
                        encoded_string = base64.b64encode(response.content).decode('utf-8')
                        new_image_data['url'] = f"data:{content_type};base64,{encoded_string}"
                    except requests.exceptions.RequestException as e:
                        print(f"Could not fetch image {new_image_data['url']}: {e}")
                        new_image_data['url'] = ''
                new_images.append(new_image_data)
            story['images'] = new_images

        html = render_template('pdf_template.html', story=story)
        
        pdf_file = BytesIO()
        pisa_status = pisa.CreatePDF(
            BytesIO(html.encode('UTF-8')),
            dest=pdf_file,
            encoding='UTF-8'
        )

        if pisa_status.err:
            return "Error creating PDF", 500

        pdf_file.seek(0)
        
        response = Response(pdf_file.read(), mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'attachment; filename="{story["title"]}.pdf"'
        return response

    return "Story not found", 404
