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

def time_to_hours(time_str):
    """Convert time strings like '90:42' to 'HH:MM' format."""
    if pd.isnull(time_str) or time_str == "---":
        return "00:00"
    try:
        # If the input has seconds, split into hours, minutes, and seconds
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, _ = map(int, parts)  # Ignore the seconds part
        elif len(parts) == 2:
            hours, minutes = map(int, parts)
        else:
            return "00:00"
        # Convert total time to HH:MM format
        total_minutes = hours * 60 + minutes
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours:02}:{minutes:02}"
    except ValueError:
        return "00:00"


def process_files(weekly_path, attendance_path, sort_option, selected_columns):
    try:
        # Load the files
        attendance_rep = pd.read_csv(attendance_path)
        weekly_attendance_report = pd.read_csv(weekly_path)

        # Standardize name formatting
        attendance_rep['Last Name'] = attendance_rep['Last Name'].str.strip().str.lower()
        attendance_rep['First Name'] = attendance_rep['First Name'].str.strip().str.lower()
        weekly_attendance_report['Last Name'] = weekly_attendance_report['StudentName'].str.split(',').str[0].str.strip().str.lower()
        weekly_attendance_report['First Name'] = weekly_attendance_report['StudentName'].str.split(',').str[1].str.strip().str.lower()

        # Process Weekly Attendance Report data
        weekly_attendance_report['Total Hours'] = weekly_attendance_report['TotalMin'].apply(time_to_hours)

        # Merge datasets
        columns_to_merge = ['Last Name', 'First Name', 'Lessons Complete', 'Difference', 'Hours Required', 'Total Hours']
        merged_data = pd.merge(
            attendance_rep[columns_to_merge],
            weekly_attendance_report[['Last Name', 'First Name', 'Total Hours']],
            on=['Last Name', 'First Name'],
            how='inner',
            suffixes=('_Cumulative', '_Weekly')
        )

        # Calculate the "Hours Ahead/Behind" column
        merged_data['Hours Ahead/Behind'] = merged_data['Total Hours_Cumulative'] - merged_data['Hours Required']

        # Sort data based on selected option
        if sort_option == 'last_first':
            merged_data.sort_values(by=['Last Name', 'First Name'], inplace=True)
        else:
            merged_data.sort_values(by=['Hours Required', 'Last Name', 'First Name'], inplace=True)

        # Limit floats to 2 decimal places
        for col in ['Total Hours_Cumulative', 'Hours Ahead/Behind']:
            if col in merged_data.columns:
                merged_data[col] = merged_data[col].round(2)

        # Rename columns
        merged_data.rename(columns={
            'Difference': 'Difference in Lessons',
            'Total Hours_Weekly': 'Weekly Hours',
            'Total Hours_Cumulative': 'Total Cumulative Hours'
        }, inplace=True)

        # Create final columns in the order of `selected_columns`
        final_columns = ['Last Name', 'First Name'] + [
            col for col in selected_columns if col in merged_data.columns
        ]

        final_data = merged_data[final_columns]

        # Insert blank lines between different values for Hours Required if sorting by hours
        output_data = []
        if sort_option != 'last_first':
            last_hours_required = None
            for _, row in merged_data.iterrows():
                if last_hours_required is not None and row['Hours Required'] != last_hours_required:
                    output_data.append({col: '' for col in final_data.columns})
                output_data.append(row[final_columns].to_dict())
                last_hours_required = row['Hours Required']
        else:
            output_data = final_data.to_dict(orient='records')

        output_df = pd.DataFrame(output_data)
        return output_df
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
            # Save the result to a CSV file in memory
            output = BytesIO()
            output_df.to_csv(output, index=False)
            output.seek(0)
            # Generate the output file name with the current date
            output_filename = f"Processed_Attendance_Report_{datetime.now().strftime('%Y-%m-%d')}.csv"
            return send_file(output, mimetype='text/csv', as_attachment=True, download_name=output_filename)
        except Exception as e:
            flash(f'An error occurred: {e}')
            return redirect(request.url)
        finally:
            # Delete the uploaded files after processing
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
