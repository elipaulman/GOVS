import sys
import os
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QMessageBox, QProgressBar, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

class FileProcessor(QThread):
    processing_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)

    def __init__(self, weekly_path, attendance_path, include_hours_behind):
        super().__init__()
        self.weekly_path = weekly_path
        self.attendance_path = attendance_path
        self.include_hours_behind = include_hours_behind

    def time_to_hours(self, time_str):
        """Convert time strings like '90:42' to decimal hours."""
        if pd.isnull(time_str) or time_str == "---":
            return 0
        try:
            hours, minutes = map(int, time_str.split(':'))
            return round(hours + minutes / 60, 2)
        except ValueError:
            return 0

    def run(self):
        try:
            # Load the files
            self.progress_updated.emit(10)
            attendance_rep = pd.read_csv(self.attendance_path)
            weekly_attendance_report = pd.read_csv(self.weekly_path)
            self.progress_updated.emit(30)

            # Standardize name formatting
            attendance_rep['Last Name'] = attendance_rep['Last Name'].str.strip().str.lower()
            attendance_rep['First Name'] = attendance_rep['First Name'].str.strip().str.lower()

            weekly_attendance_report['Last Name'] = weekly_attendance_report['StudentName'].str.split(',').str[0].str.strip().str.lower()
            weekly_attendance_report['First Name'] = weekly_attendance_report['StudentName'].str.split(',').str[1].str.strip().str.lower()
            self.progress_updated.emit(50)

            # Process Weekly Attendance Report data
            weekly_attendance_report['Total Hours'] = weekly_attendance_report['TotalMin'].apply(self.time_to_hours)

            # Merge datasets
            merged_data = pd.merge(
                attendance_rep[['Last Name', 'First Name', 'Lessons Complete', 'Difference', 'Hours Required', 'Total Hours']],
                weekly_attendance_report[['Last Name', 'First Name', 'Total Hours']],
                on=['Last Name', 'First Name'],
                how='inner',
                suffixes=('_Cumulative', '_Weekly')
            )
            self.progress_updated.emit(70)

            # Sort by Hours Required, then by Last Name and First Name
            merged_data.sort_values(by=['Hours Required', 'Last Name', 'First Name'], inplace=True)

            # Limit floats to 2 decimal places
            merged_data['Total Hours_Weekly'] = merged_data['Total Hours_Weekly'].round(2)

            # Rename columns
            merged_data.rename(columns={
                'Difference': 'Difference in Lessons',
                'Total Hours_Weekly': 'Weekly Hours',
                'Total Hours_Cumulative': 'Total Cumulative Hours'
            }, inplace=True)

            # Calculate Hours Behind/Ahead if selected
            if self.include_hours_behind:
                merged_data['Hours Behind/Ahead'] = merged_data['Total Cumulative Hours'] - merged_data['Hours Required']

            # Select the required columns with swapped positions
            columns = ['Last Name', 'First Name', 'Lessons Complete', 'Difference in Lessons', 'Weekly Hours', 'Total Cumulative Hours', 'Hours Required']
            if self.include_hours_behind:
                columns.append('Hours Behind/Ahead')
            final_data = merged_data[columns]

            # Insert blank lines between different values for Hours Required
            output_data = []
            last_hours_required = None
            for _, row in final_data.iterrows():
                if last_hours_required is not None and row['Hours Required'] != last_hours_required:
                    output_data.append({col: '' for col in final_data.columns})
                output_data.append(row.to_dict())
                last_hours_required = row['Hours Required']

            output_df = pd.DataFrame(output_data)

            # Save the result to a CSV file in the Downloads folder
            downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
            output_path = os.path.join(downloads_folder, "Sorted_Attendance_Report.csv")
            output_df.to_csv(output_path, index=False)
            self.progress_updated.emit(100)

            self.processing_complete.emit(f"Output file saved to {output_path}")

        except Exception as e:
            self.error_occurred.emit(str(e))

class AttendanceProcessorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Attendance Report Processor')
        self.setGeometry(100, 100, 500, 400)

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # File Selection Layouts
        weekly_layout = QHBoxLayout()
        attendance_layout = QHBoxLayout()
        main_layout.addLayout(weekly_layout)
        main_layout.addLayout(attendance_layout)

        # Weekly Attendance Report
        self.weekly_label = QLabel('Weekly Attendance Report: Not Selected')
        self.weekly_button = QPushButton('Select File')
        self.weekly_button.clicked.connect(self.select_weekly_file)
        weekly_layout.addWidget(self.weekly_label)
        weekly_layout.addWidget(self.weekly_button)

        # Attendance Report
        self.attendance_label = QLabel('Attendance Report: Not Selected')
        self.attendance_button = QPushButton('Select File')
        self.attendance_button.clicked.connect(self.select_attendance_file)
        attendance_layout.addWidget(self.attendance_label)
        attendance_layout.addWidget(self.attendance_button)

        # Checkbox for Hours Behind/Ahead
        self.include_hours_checkbox = QCheckBox("Include Hours Behind/Ahead")
        main_layout.addWidget(self.include_hours_checkbox)

        # Process Button
        self.process_button = QPushButton('Process Files')
        self.process_button.clicked.connect(self.process_files)
        self.process_button.setEnabled(False)
        main_layout.addWidget(self.process_button)

        # Progress Bar
        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)

        # Status Label
        self.status_label = QLabel('')
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        # Instance variables for file paths
        self.weekly_file_path = None
        self.attendance_file_path = None

    def select_weekly_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Weekly Attendance Report", "", "CSV Files (*.csv);;Excel Files (*.xlsx)")
        if file_path:
            self.weekly_file_path = file_path
            self.weekly_label.setText(f'Weekly File: {os.path.basename(file_path)}')
            self.check_files_selected()

    def select_attendance_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Attendance Report", "", "CSV Files (*.csv);;Excel Files (*.xlsx)")
        if file_path:
            self.attendance_file_path = file_path
            self.attendance_label.setText(f'Attendance File: {os.path.basename(file_path)}')
            self.check_files_selected()

    def check_files_selected(self):
        if self.weekly_file_path and self.attendance_file_path:
            self.process_button.setEnabled(True)

    def process_files(self):
        # Disable buttons during processing
        self.weekly_button.setEnabled(False)
        self.attendance_button.setEnabled(False)
        self.process_button.setEnabled(False)

        # Reset progress and status
        self.progress_bar.setValue(0)
        self.status_label.setText('')

        # Create and start processing thread
        include_hours_behind = self.include_hours_checkbox.isChecked()
        self.processor_thread = FileProcessor(self.weekly_file_path, self.attendance_file_path, include_hours_behind)
        self.processor_thread.processing_complete.connect(self.on_processing_complete)
        self.processor_thread.error_occurred.connect(self.on_processing_error)
        self.processor_thread.progress_updated.connect(self.update_progress)
        self.processor_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def on_processing_complete(self, message):
        QMessageBox.information(self, "Processing Complete", message)
        self.status_label.setText("Processing Complete!")

        # Re-enable buttons
        self.weekly_button.setEnabled(True)
        self.attendance_button.setEnabled(True)
        self.weekly_file_path = None
        self.attendance_file_path = None

        # Reset labels
        self.weekly_label.setText('Weekly Attendance Report: Not Selected')
        self.attendance_label.setText('Attendance Report: Not Selected')
        self.process_button.setEnabled(False)

    def on_processing_error(self, error):
        QMessageBox.critical(self, "Processing Error", str(error))
        self.status_label.setText("Processing Failed!")

        # Re-enable buttons
        self.weekly_button.setEnabled(True)
        self.attendance_button.setEnabled(True)
        self.process_button.setEnabled(False)

def main():
    app = QApplication(sys.argv)
    main_window = AttendanceProcessorApp()
    main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
