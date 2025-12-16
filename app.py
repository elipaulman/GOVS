import logging
import os
import shutil
import tempfile
from datetime import datetime
from io import BytesIO

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
default_upload_root = '/tmp/uploads' if os.name != 'nt' else os.path.join(os.getcwd(), 'uploads')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', default_upload_root)
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'xlsx'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production' or bool(os.environ.get('RENDER'))

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

if app.secret_key == 'dev-secret-key-change-me':
    logger.warning('SECRET_KEY is using the fallback value. Set SECRET_KEY for production deployments.')

REQUIRED_WEEKLY_COLUMNS = {'StudentName', 'TotalMin'}
REQUIRED_ATTENDANCE_COLUMNS = {'Last Name', 'First Name', 'Lessons Complete', 'Difference', 'Hours Required', 'Total Hours'}
NUMERIC_COLUMNS = ('Lessons Complete', 'Difference', 'Hours Required', 'Total Hours')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def validate_required_columns(df, required_columns, source_label):
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"{source_label} missing required columns: {', '.join(missing)}")


def load_report(path, is_weekly=False):
    """
    Load CSV or XLSX into a DataFrame. Weekly report keeps TotalMin as string so
    we can safely normalize time values before computation.
    """
    _, ext = os.path.splitext(path.lower())
    if ext == '.xlsx':
        df = pd.read_excel(path, engine='openpyxl')
    else:
        df = pd.read_csv(path)

    if is_weekly and 'TotalMin' in df.columns:
        df['TotalMin'] = df['TotalMin'].astype(str)
    return df

def normalize_attendance_names(attendance_rep):
    attendance_rep['Last Name'] = attendance_rep['Last Name'].str.strip().str.lower()
    attendance_rep['First Name'] = attendance_rep['First Name'].str.strip().str.lower()


def normalize_weekly_names(weekly_report):
    name_split = weekly_report['StudentName'].str.split(',', n=1, expand=True)
    weekly_report['Last Name'] = name_split[0].str.strip().str.lower()
    weekly_report['First Name'] = name_split[1].fillna('').str.strip().str.lower()
    if weekly_report['First Name'].eq('').any():
        raise ValueError("Weekly report names must use 'Last, First' format in the StudentName column.")


def convert_numeric_columns(df, columns, source_label):
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    invalid_columns = [col for col in columns if df[col].isnull().any()]
    if invalid_columns:
        raise ValueError(f"{source_label} has non-numeric values in: {', '.join(invalid_columns)}")


def time_to_hours(time_val):
    """Convert time values (e.g., '25:04:00', '8:32') to 'HH:MM' format."""
    if pd.isnull(time_val) or str(time_val).strip() in ("---", "", "nan"):
        return "00:00"
    try:
        # Convert to string and strip whitespace
        time_str = str(time_val).strip()
        # Split into parts (could be HH:MM:SS or H:MM)
        parts = time_str.split(':')
        # Extract hours and minutes (ignore seconds)
        hours = int(parts[0]) if len(parts) >= 1 else 0
        minutes = int(parts[1]) if len(parts) >= 2 else 0
        # Calculate total minutes
        total_minutes = (hours * 60) + minutes
        # Convert back to HH:MM
        formatted_hours = total_minutes // 60
        formatted_minutes = total_minutes % 60
        return f"{formatted_hours:02}:{formatted_minutes:02}"
    except Exception as e:
        logging.error(f"Failed to parse time: {time_val}. Error: {e}")
        return "00:00"

def format_hours_minutes(hours_minutes_str):
    """Format hours and minutes to [h]:mm format."""
    try:
        hours, minutes = map(int, hours_minutes_str.split(':'))
        return f"{hours}:{minutes:02}"
    except Exception as e:
        logging.error(f"Failed to format hours and minutes: {hours_minutes_str}. Error: {e}")
        return "0:00"

def process_files(weekly_path, attendance_path, sort_option, selected_columns):
    try:
        # Load files
        attendance_rep = load_report(attendance_path)
        weekly_report = load_report(weekly_path, is_weekly=True)  # Keep TotalMin as strings for consistent parsing

        validate_required_columns(attendance_rep, REQUIRED_ATTENDANCE_COLUMNS, 'Attendance report')
        validate_required_columns(weekly_report, REQUIRED_WEEKLY_COLUMNS, 'Weekly report')

        # Standardize names
        normalize_attendance_names(attendance_rep)
        normalize_weekly_names(weekly_report)
        convert_numeric_columns(attendance_rep, NUMERIC_COLUMNS, 'Attendance report')

        # Process Weekly Hours (from "TotalMin" column)
        weekly_report['Weekly Hours'] = weekly_report['TotalMin'].apply(time_to_hours)

        # Merge datasets
        merged_data = pd.merge(
            attendance_rep[['Last Name', 'First Name', 'Lessons Complete', 'Difference', 'Hours Required', 'Total Hours']],
            weekly_report[['Last Name', 'First Name', 'Weekly Hours']],
            on=['Last Name', 'First Name'],
            how='inner'
        )

        # Calculate "Hours Ahead/Behind"
        merged_data['Hours Ahead/Behind'] = merged_data['Total Hours'] - merged_data['Hours Required']

        # Sort data
        if sort_option not in ('last_first', 'hours_last_first'):
            sort_option = 'hours_last_first'
        if sort_option == 'last_first':
            merged_data.sort_values(by=['Last Name', 'First Name'], inplace=True)
        else:
            merged_data.sort_values(by=['Hours Required', 'Last Name', 'First Name'], inplace=True)

        # Round numeric columns
        for col in ['Total Hours', 'Hours Ahead/Behind']:
            merged_data[col] = merged_data[col].round(2)

        # Rename columns
        merged_data.rename(columns={
            'Difference': 'Difference in Lessons',
            'Total Hours': 'Total Cumulative Hours'
        }, inplace=True)

        # Format Weekly Hours to [h]:mm
        merged_data['Weekly Hours'] = merged_data['Weekly Hours'].apply(format_hours_minutes)

        # Select final columns
        final_columns = ['Last Name', 'First Name'] + [col for col in selected_columns if col in merged_data.columns]
        final_data = merged_data[final_columns]

        # Insert blank lines if sorting by hours
        output_data = []
        if sort_option != 'last_first':
            last_hours_required = None
            for _, row in merged_data.iterrows():
                if last_hours_required is not None and row['Hours Required'] != last_hours_required:
                    output_data.append({col: '' for col in final_columns})
                output_data.append(row[final_columns].to_dict())
                last_hours_required = row['Hours Required']
        else:
            output_data = final_data.to_dict(orient='records')

        return pd.DataFrame(output_data)
    except Exception as e:
        logger.error(f'Error processing files: {e}')
        raise

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'weekly_file' not in request.files or 'attendance_file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        weekly_file = request.files['weekly_file']
        attendance_file = request.files['attendance_file']
        sort_option = request.form.get('sort_option', 'hours_last_first')
        selected_columns = request.form.getlist('columns')
        if not selected_columns:
            flash('Please select at least one column.')
            return redirect(request.url)
        if weekly_file.filename == '' or attendance_file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if not allowed_file(weekly_file.filename) or not allowed_file(attendance_file.filename):
            flash('Invalid file type. Only CSV and Excel files are allowed.')
            return redirect(request.url)
        
        temp_dir = tempfile.mkdtemp(dir=app.config['UPLOAD_FOLDER'])
        weekly_filename = secure_filename(weekly_file.filename)
        attendance_filename = secure_filename(attendance_file.filename)
        weekly_path = os.path.join(temp_dir, weekly_filename)
        attendance_path = os.path.join(temp_dir, attendance_filename)
        
        try:
            with open(weekly_path, 'wb') as wf, open(attendance_path, 'wb') as af:
                wf.write(weekly_file.read())
                af.write(attendance_file.read())
            
            output_df = process_files(weekly_path, attendance_path, sort_option, selected_columns)
            output = BytesIO()
            output_df.to_csv(output, index=False)
            output.seek(0)
            output_filename = f"Processed_Attendance_Report_{datetime.now().strftime('%Y-%m-%d')}.csv"
            return send_file(output, mimetype='text/csv', as_attachment=True, download_name=output_filename)
        except Exception as e:
            flash(f'An error occurred: {e}')
            return redirect(request.url)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    return render_template('index.html')

@app.route('/instructions')
def instructions():
    return render_template('instructions.html')


@app.route('/healthz')
def healthz():
    return {'status': 'ok'}, 200


if __name__ == '__main__':
    # For local development only
    # In production, Gunicorn will run the app via render.yaml
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
