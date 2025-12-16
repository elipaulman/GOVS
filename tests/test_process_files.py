import pandas as pd
import pytest

from app import process_files


def test_process_files_with_csv(tmp_path):
    weekly_path = tmp_path / "weekly.csv"
    attendance_path = tmp_path / "attendance.csv"

    pd.DataFrame(
        {
            "StudentName": ["doe, john"],
            "TotalMin": ["90:30"],
        }
    ).to_csv(weekly_path, index=False)

    pd.DataFrame(
        {
            "Last Name": ["doe"],
            "First Name": ["john"],
            "Lessons Complete": [10],
            "Difference": [2],
            "Hours Required": [10],
            "Total Hours": [12.5],
        }
    ).to_csv(attendance_path, index=False)

    selected_columns = [
        "Weekly Hours",
        "Lessons Complete",
        "Difference in Lessons",
        "Total Cumulative Hours",
        "Hours Required",
        "Hours Ahead/Behind",
    ]
    result = process_files(
        str(weekly_path), str(attendance_path), "hours_last_first", selected_columns
    )

    assert list(result.columns) == ["Last Name", "First Name"] + selected_columns
    row = result.iloc[0]
    assert row["Weekly Hours"] == "90:30"
    assert row["Hours Ahead/Behind"] == 2.5


def test_process_files_with_excel(tmp_path):
    weekly_path = tmp_path / "weekly.xlsx"
    attendance_path = tmp_path / "attendance.xlsx"

    pd.DataFrame(
        {
            "StudentName": ["smith, jane"],
            "TotalMin": ["05:15"],
        }
    ).to_excel(weekly_path, index=False)

    pd.DataFrame(
        {
            "Last Name": ["smith"],
            "First Name": ["jane"],
            "Lessons Complete": [8],
            "Difference": [1],
            "Hours Required": [6],
            "Total Hours": [7.25],
        }
    ).to_excel(attendance_path, index=False)

    selected_columns = [
        "Weekly Hours",
        "Lessons Complete",
        "Difference in Lessons",
        "Total Cumulative Hours",
        "Hours Required",
        "Hours Ahead/Behind",
    ]
    result = process_files(
        str(weekly_path), str(attendance_path), "last_first", selected_columns
    )

    assert list(result.columns) == ["Last Name", "First Name"] + selected_columns
    row = result.iloc[0]
    assert row["Weekly Hours"] == "5:15"


def test_process_files_missing_columns(tmp_path):
    weekly_path = tmp_path / "weekly.csv"
    attendance_path = tmp_path / "attendance.csv"

    pd.DataFrame(
        {
            "StudentName": ["doe, john"],
            # Missing TotalMin on purpose
        }
    ).to_csv(weekly_path, index=False)

    pd.DataFrame(
        {
            "Last Name": ["doe"],
            "First Name": ["john"],
            "Lessons Complete": [10],
            "Difference": [2],
            "Hours Required": [10],
            "Total Hours": [12.5],
        }
    ).to_csv(attendance_path, index=False)

    with pytest.raises(ValueError, match="Weekly report missing required columns: TotalMin"):
        process_files(
            str(weekly_path), str(attendance_path), "hours_last_first", ["Weekly Hours"]
        )


def test_process_files_non_numeric_columns(tmp_path):
    weekly_path = tmp_path / "weekly.csv"
    attendance_path = tmp_path / "attendance.csv"

    pd.DataFrame(
        {
            "StudentName": ["doe, john"],
            "TotalMin": ["01:00"],
        }
    ).to_csv(weekly_path, index=False)

    pd.DataFrame(
        {
            "Last Name": ["doe"],
            "First Name": ["john"],
            "Lessons Complete": ["ten"],  # non-numeric on purpose
            "Difference": [2],
            "Hours Required": [10],
            "Total Hours": [12.5],
        }
    ).to_csv(attendance_path, index=False)

    with pytest.raises(ValueError, match="Attendance report has non-numeric values in: Lessons Complete"):
        process_files(
            str(weekly_path), str(attendance_path), "hours_last_first", ["Weekly Hours"]
        )
