# Attendance Report Processing Tool

A web application built for **Greater Ohio Virtual School** to automate the merging and processing of student attendance reports. The tool combines weekly activity reports with cumulative attendance data to generate comprehensive reports with calculated metrics.

🔗 **Live Application**: [https://govs-csv-processor.onrender.com/](https://govs-csv-processor.onrender.com/)

## Overview

This Flask-based application processes two types of student reports:
1. **Weekly Report** - Contains weekly activity data with time spent per student
2. **Attendance Report** - Contains cumulative data including lessons completed, hours required, and total hours

The app merges these reports, normalizes student names, calculates hours ahead/behind schedule, and exports a consolidated CSV report.

## Key Features

- **File Upload**: Supports CSV and Excel (.xlsx) file uploads (max 16 MB)
- **Intelligent Merging**: Automatically matches students across reports using name normalization
- **Data Processing**:
  - Converts time formats to standardized HH:MM format
  - Calculates hours ahead/behind schedule
  - Handles edge cases (missing data, malformed time values)
- **Flexible Output**:
  - Customizable column selection and ordering
  - Multiple sorting options (by name or hours required)
  - Auto-inserts blank rows to group students by hours when sorted by hours
- **Modern UI**: Clean web interface with light/dark mode toggle
- **Instant Export**: Generates timestamped CSV files for download

## For Users

### Using the Application

1. Navigate to the application URL
2. Click **Instructions** for detailed guidance on preparing your files
3. Upload two files:
   - Weekly report (must contain `StudentName` and `TotalMin` columns)
   - Attendance report (must contain student names, lessons, hours data)
4. Select desired columns for the output report
5. Choose sorting preference (alphabetical or by hours required)
6. Click **Process Files** to generate and download your report

### Output Report Columns

The generated report includes:
- **Last Name** / **First Name**: Student identifiers
- **Lessons Complete**: Total lessons finished
- **Difference in Lessons**: Gap in lesson completion
- **Hours Required**: Expected hours at this point
- **Total Cumulative Hours**: All-time hours logged
- **Weekly Hours**: Hours from the most recent week (in [h]:mm format)
- **Hours Ahead/Behind**: Calculated difference between total and required hours

## For Developers

### Prerequisites

- Python 3.11+
- pip package manager
- (Recommended) A virtual environment for dependency isolation

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd GOVS
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables** (optional)
   ```bash
   export SECRET_KEY="your-secret-key-here"
   export UPLOAD_FOLDER="/path/to/uploads"  # Defaults to ./uploads on Windows, /tmp/uploads on Unix
   export LOG_LEVEL="INFO"                   # Optional: configure server logging
   ```

5. **Run the development server**
   ```bash
   python app.py
   ```
   The app will be available at `http://localhost:10000`

### Running Tests

```bash
pytest
```

Tests cover the core `process_files` function and data processing logic.

### Project Structure

```
GOVS/
├── app.py                  # Main Flask application
├── gunicorn_config.py      # Production server configuration
├── requirements.txt        # Python dependencies
├── render.yaml            # Render.com deployment config
├── templates/
│   ├── index.html         # Main upload interface
│   └── instructions.html  # User instructions page
└── tests/
    └── test_process_files.py  # Unit tests
```

### Key Functions

- **`load_report(path, is_weekly)`**: Loads CSV/Excel files into pandas DataFrames
- **`time_to_hours(time_val)`**: Normalizes time values to HH:MM format
- **`process_files(...)`**: Core logic for merging, calculating, and formatting reports
- **`allowed_file(filename)`**: Validates file extensions

### Technology Stack

- **Backend**: Flask 3.0.3, Python 3.11
- **Data Processing**: Pandas 2.2.2, NumPy 2.0.1
- **File Handling**: openpyxl 3.1.5 (Excel support)
- **Production Server**: Gunicorn 22.0.0
- **Testing**: pytest 8.3.2

## Deployment

### Render.com Deployment

The application is configured for deployment on Render.com:

1. **Service Configuration**: Defined in [render.yaml](render.yaml)
   - Python 3.11 environment
   - Free tier plan
   - Starts via Gunicorn with custom configuration and health check at `/healthz`

2. **Required Environment Variables** (set in Render dashboard):
   - `SECRET_KEY`: Required for Flask sessions and flash messages
   - `UPLOAD_FOLDER`: File upload directory (defaults to `/tmp/uploads`)
   - Optional: `LOG_LEVEL`, `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`

3. **Deployment Process**:
   - Push code to connected Git repository
   - Render automatically runs `pip install -r requirements.txt`
   - Starts the app with `gunicorn -c gunicorn_config.py app:app`

4. **Health Check**: Available at `/healthz` endpoint

### Other Platforms

The app can be deployed to any platform supporting Python web applications:
- Heroku: Use the Procfile format
- AWS/GCP: Deploy with Docker or native Python support
- Traditional hosting: Run with Gunicorn or uWSGI behind nginx/Apache

## License

MIT License
