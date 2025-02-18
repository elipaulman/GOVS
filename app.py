import os
import pandas as pd
from flask import Flask, request, render_template, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from io import BytesIO
from datetime import datetime
import logging

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'xlsx'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

logging.basicConfig(level=logging.INFO)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def time_to_hours(time_val):
    """Convert time values (e.g., '25:04:00', '8:32') to 'HH:MM' format."""
    if pd.isnull(time_val) or str(time_val).strip() in ("---", "", "nan"):
        return "00:00"
    try:
        # Convert to string and strip whitespace
        time_str = str(time_val).strip()
        # Split into parts (could be HH:MM:SS or H:MM)
        parts = time_str.split(':')
        elif len(parts) == 2:
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
        attendance_rep = pd.read_csv(attendance_path)
        weekly_report = pd.read_csv(weekly_path, dtype={'TotalMin': str})  # Read as string to avoid auto-parsing

        # Standardize names
        attendance_rep['Last Name'] = attendance_rep['Last Name'].str.strip().str.lower()
        attendance_rep['First Name'] = attendance_rep['First Name'].str.strip().str.lower()
        weekly_report['Last Name'] = weekly_report['StudentName'].str.split(',').str[0].str.strip().str.lower()
        weekly_report['First Name'] = weekly_report['StudentName'].str.split(',').str[1].str.strip().str.lower()

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
            output_data = merged_data.to_dict(orient='records')

        return pd.DataFrame(output_data)
    except Exception as e:
        logging.error(f'Error processing files: {e}')
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
        
        weekly_filename = secure_filename(weekly_file.filename)
        attendance_filename = secure_filename(attendance_file.filename)
        weekly_path = os.path.join(app.config['UPLOAD_FOLDER'], weekly_filename)
        attendance_path = os.path.join(app.config['UPLOAD_FOLDER'], attendance_filename)
        
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
            if os.path.exists(weekly_path):
                os.remove(weekly_path)
            if os.path.exists(attendance_path):
                os.remove(attendance_path)
    return render_template('index.html')

@app.route('/instructions')
def instructions():
    return render_template('instructions.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)