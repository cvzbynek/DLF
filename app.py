from flask import Flask, render_template, request, redirect, url_for
import os
from werkzeug.utils import secure_filename

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)
ALLOWED_EXTENSIONS = {'pdf'}

# === CONFIGURATION ===
GOOGLE_DRIVE_FOLDER_ID = '148AHAnm100uQ4wgajcMWwR-qNEswPdCT'
CREDENTIALS_FILE = '/home/dlf/www/credentials.json'

# === Google API setup ===
scope = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)

# Google Sheets
gs_client = gspread.authorize(creds)
sheet = gs_client.open_by_key('10U6GB_rPiGu-GNqj_bWbOhdycWJYCDkobZoICOX4SHc').sheet1


# === Utility functions ===
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_file_to_drive(filename, file_storage, mimetype, folder_id):
    # Save file temporarily
    temp_path = f"/tmp/{filename}"
    file_storage.save(temp_path)

    # Upload to Drive
    drive_service = build('drive', 'v3', credentials=creds)
    file_metadata = {'name': filename, 'parents': [folder_id]}
    media = MediaFileUpload(temp_path, mimetype=mimetype)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

    # Make public
    drive_service.permissions().create(fileId=file['id'], body={'type': 'anyone', 'role': 'reader'}).execute()

    # Remove temp file
    os.remove(temp_path)

    return f"https://drive.google.com/file/d/{file['id']}/view?usp=sharing"


# === Flask routes ===
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register')
def register():
    return render_template('form.html')


@app.route('/submit', methods=['POST'])
def submit():
    form = request.form
    files = request.files

    # === Teacher recommendation (required) ===
    rec_file = files.get('teacher_recommendation')
    if rec_file and allowed_file(rec_file.filename):
        rec_url = upload_file_to_drive(secure_filename(rec_file.filename), rec_file, 'application/pdf', GOOGLE_DRIVE_FOLDER_ID)
    else:
        return "Chybí platný soubor doporučení učitele (PDF).", 400

    # === GDPR consent (conditionally required) ===
    gdpr_url = ''
    if form.get('consent_gdpr') == 'neplnoletý PDF':
        gdpr_file = files.get('gdpr_consent')
        if gdpr_file and allowed_file(gdpr_file.filename):
            gdpr_url = upload_file_to_drive(secure_filename(gdpr_file.filename), gdpr_file, 'application/pdf', GOOGLE_DRIVE_FOLDER_ID)
        else:
            return "Chybí GDPR souhlas (PDF).", 400

    # === Radiation zone consent (optional) ===
    controlled_url = ''
    controlled_file = files.get('controlled_area_consent')
    if controlled_file and allowed_file(controlled_file.filename):
        controlled_url = upload_file_to_drive(secure_filename(controlled_file.filename), controlled_file, 'application/pdf', GOOGLE_DRIVE_FOLDER_ID)

    # === Prepare row for sheet ===
    row = [
        form['email'],
        form['first_name'],
        form['last_name'],
        form.get('school_type', ''),
        form.get('school_name', ''),
        form.get('graduation_year', ''),
        form.get('considering_fjfi', ''),
        ', '.join(form.getlist('source')),
        form['first_choice_exercise'],
        form.get('second_choice_exercise', ''),
        form['first_excursion'],
        form.get('second_excursion', ''),
        form['alternative_excursion_ok'],
        rec_url,
        controlled_url,
        form.get('consent_gdpr', ''),
        gdpr_url,
        form.get('confirm_truth', 'ano')
    ]

    sheet.append_row([str(cell) for cell in row], value_input_option="USER_ENTERED")
    return redirect(url_for('success'))


@app.route('/success')
def success():
    return render_template('success.html')


if __name__ == '__main__':
    app.run(debug=True)
