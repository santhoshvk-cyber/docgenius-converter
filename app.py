# Final app.py with all advanced features

from flask import Flask, render_template, request, send_file, redirect, url_for, flash
import os
import uuid
import time
import logging
from werkzeug.utils import secure_filename
from pdf2docx import Converter
import aspose.words as aw
import smtplib
from email.message import EmailMessage
from threading import Thread

# Configuration
UPLOAD_FOLDER = 'uploads'
CONVERTED_FOLDER = 'converted'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
MAX_FILE_SIZE_MB = 25  # Limit file size

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER
app.secret_key = 'super_secret_key'

# Setup Logging
logging.basicConfig(level=logging.INFO)

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

# Utility Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_filename(extension):
    return f"{uuid.uuid4().hex}.{extension}"

def clean_old_files(folder, age_limit=900):  # 15 minutes
    now = time.time()
    for f in os.listdir(folder):
        path = os.path.join(folder, f)
        if os.path.isfile(path) and now - os.path.getmtime(path) > age_limit:
            os.remove(path)

def send_email_with_attachment_async(to_email, file_path):
    def send():
        try:
            EMAIL_ADDRESS = os.environ.get('EMAIL_USER')
            EMAIL_PASSWORD = os.environ.get('EMAIL_PASS')
            if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
                logging.warning("Email credentials not set.")
                return

            msg = EmailMessage()
            msg['Subject'] = 'Your DocGenius Converted File'
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = to_email
            msg.set_content('Attached is your converted file. Thank you for using DocGenius.')

            with open(file_path, 'rb') as f:
                file_data = f.read()
                file_name = os.path.basename(file_path)
                msg.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)
            logging.info(f"Email sent to {to_email}")
        except Exception as e:
            logging.error(f"Failed to send email: {e}")

    Thread(target=send).start()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_file():
    file = request.files.get('file')
    conversion_type = request.form.get('conversion_type')
    email = request.form.get('email')

    if not file or file.filename == '':
        flash('No file selected.')
        return redirect(url_for('index'))

    if not allowed_file(file.filename):
        flash('Unsupported file type.')
        return redirect(url_for('index'))

    if len(file.read()) > MAX_FILE_SIZE_MB * 1024 * 1024:
        flash('File too large. Max 25MB.')
        return redirect(url_for('index'))
    file.seek(0)

    clean_old_files(UPLOAD_FOLDER)
    clean_old_files(CONVERTED_FOLDER)

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    input_path = os.path.join(UPLOAD_FOLDER, generate_filename(ext))
    file.save(input_path)

    output_ext = 'pdf' if conversion_type == 'word-to-pdf' else 'docx'
    output_filename = generate_filename(output_ext)
    output_path = os.path.join(CONVERTED_FOLDER, output_filename)

    try:
        if conversion_type == 'word-to-pdf':
            doc = aw.Document(input_path)
            doc.save(output_path)
        elif conversion_type == 'pdf-to-word':
            cv = Converter(input_path)
            cv.convert(output_path, start=0, end=None)
            cv.close()
        else:
            flash('Invalid conversion type.')
            return redirect(url_for('index'))

        if email:
            send_email_with_attachment_async(email, output_path)

        return render_template('result.html', download_file=output_filename, email=email)

    except Exception as e:
        logging.error(f"Conversion failed: {e}")
        flash('Conversion failed. Try another file.')
        return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(CONVERTED_FOLDER, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    else:
        flash('File not found or expired.')
        return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
