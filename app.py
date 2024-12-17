import os
import pandas as pd
from flask import Flask, request, render_template, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'xlsx'}

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def time_to_hours(time_str):
    """Convert time strings like '90:42' to decimal hours."""
    if pd.isnull(time_str) or time_str == "---":
        return 0
    try:
        hours, minutes = map(int, time_str.split(':'))
        return round(hours + minutes / 60, 2)
    except ValueError:
        return 0

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'weekly_file' not in request.files or 'attendance_file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        weekly_file = request.files['weekly_file']
        attendance_file = request.files['attendance_file']
        sort_option = request.form.get('sort_option', 'hours_last_first')
        if weekly_file.filename == '' or attendance_file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if allowed_file(weekly_file.filename) and allowed_file(attendance_file.filename):
            weekly_filename = secure_filename(weekly_file.filename)
            attendance_filename = secure_filename(attendance_file.filename)
            weekly_path = os.path.join(app.config['UPLOAD_FOLDER'], weekly_filename)
            attendance_path = os.path.join(app.config['UPLOAD_FOLDER'], attendance_filename)
            weekly_file.save(weekly_path)
            attendance_file.save(attendance_path)
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
                merged_data = pd.merge(
                    attendance_rep[['Last Name', 'First Name', 'Lessons Complete', 'Difference', 'Hours Required', 'Total Hours']],
                    weekly_attendance_report[['Last Name', 'First Name', 'Total Hours']],
                    on=['Last Name', 'First Name'],
                    how='inner',
                    suffixes=('_Cumulative', '_Weekly')
                )
                # Sort data based on selected option
                if sort_option == 'last_first':
                    merged_data.sort_values(by=['Last Name', 'First Name'], inplace=True)
                else:
                    merged_data.sort_values(by=['Hours Required', 'Last Name', 'First Name'], inplace=True)
                # Limit floats to 2 decimal places
                merged_data['Total Hours_Weekly'] = merged_data['Total Hours_Weekly'].round(2)
                # Rename columns
                merged_data.rename(columns={
                    'Difference': 'Difference in Lessons',
                    'Total Hours_Weekly': 'Weekly Hours',
                    'Total Hours_Cumulative': 'Total Cumulative Hours'
                }, inplace=True)
                # Select the required columns with swapped positions
                final_data = merged_data[['Last Name', 'First Name', 'Lessons Complete', 'Difference in Lessons', 'Weekly Hours', 'Total Cumulative Hours', 'Hours Required']]
                # Insert blank lines between different values for Hours Required if sorting by hours
                output_data = []
                if sort_option != 'last_first':
                    last_hours_required = None
                    for _, row in final_data.iterrows():
                        if last_hours_required is not None and row['Hours Required'] != last_hours_required:
                            output_data.append({col: '' for col in final_data.columns})
                        output_data.append(row.to_dict())
                        last_hours_required = row['Hours Required']
                else:
                    output_data = final_data.to_dict(orient='records')
                output_df = pd.DataFrame(output_data)
                # Save the result to a CSV file in memory
                output = BytesIO()
                output_df.to_csv(output, index=False)
                output.seek(0)
                return send_file(output, mimetype='text/csv', as_attachment=True, download_name='Sorted_Attendance_Report.csv')
            except Exception as e:
                flash(f'An error occurred: {e}')
                return redirect(request.url)
    return render_template('index.html')

@app.route('/instructions')
def instructions():
    return render_template('instructions.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)