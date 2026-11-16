"""Route-level tests for the Flask app.

Written with unittest so they run under both `python -m unittest` and pytest.
They cover the behavior that existed before the privacy notice was added
(pages load, uploads validate, reports download, temp files are deleted)
and the privacy notice itself.
"""
import os
import re
import shutil
import tempfile
import unittest
from io import BytesIO

# Point uploads at a throwaway folder before the app is imported.
_UPLOAD_ROOT = tempfile.mkdtemp(prefix="govs-test-uploads-")
os.environ["UPLOAD_FOLDER"] = _UPLOAD_ROOT

from app import allowed_file, app  # noqa: E402

WEEKLY_CSV = b"StudentName,TotalMin\n\"doe, john\",90:30\n"
ATTENDANCE_CSV = (
    b"Last Name,First Name,Lessons Complete,Difference,Hours Required,Total Hours\n"
    b"doe,john,10,2,10,12.5\n"
)
COLUMNS = [
    "Weekly Hours",
    "Lessons Complete",
    "Difference in Lessons",
    "Total Cumulative Hours",
    "Hours Required",
    "Hours Ahead/Behind",
]


def tearDownModule():
    shutil.rmtree(_UPLOAD_ROOT, ignore_errors=True)


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def post_files(self, weekly=("weekly.csv", WEEKLY_CSV),
                   attendance=("attendance.csv", ATTENDANCE_CSV),
                   columns=COLUMNS, sort="hours_last_first", follow=False):
        data = {"sort_option": sort, "columns": columns}
        if weekly is not None:
            data["weekly_file"] = (BytesIO(weekly[1]), weekly[0])
        if attendance is not None:
            data["attendance_file"] = (BytesIO(attendance[1]), attendance[0])
        return self.client.post(
            "/", data=data, content_type="multipart/form-data",
            follow_redirects=follow,
        )


class PageTests(RouteTestCase):
    def test_upload_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Attendance Processor", html)
        self.assertIn('name="weekly_file"', html)
        self.assertIn('name="attendance_file"', html)

    def test_instructions_page_loads(self):
        response = self.client.get("/instructions")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Back to Upload", response.get_data(as_text=True))

    def test_health_check(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_unknown_route_is_404(self):
        self.assertEqual(self.client.get("/nope").status_code, 404)


class UploadTests(RouteTestCase):
    def test_allowed_file_extensions(self):
        self.assertTrue(allowed_file("report.csv"))
        self.assertTrue(allowed_file("REPORT.XLSX"))
        self.assertFalse(allowed_file("report.pdf"))
        self.assertFalse(allowed_file("report"))

    def test_missing_files_redirects_with_message(self):
        response = self.post_files(weekly=None, attendance=None, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("No file part", response.get_data(as_text=True))

    def test_invalid_file_type_is_rejected(self):
        response = self.post_files(weekly=("weekly.pdf", b"x"), follow=True)
        self.assertIn("Invalid file type", response.get_data(as_text=True))

    def test_no_columns_selected_is_rejected(self):
        response = self.post_files(columns=[], follow=True)
        self.assertIn("select at least one column", response.get_data(as_text=True))

    def test_bad_report_shows_error_instead_of_crashing(self):
        response = self.post_files(weekly=("weekly.csv", b"Wrong\n1\n"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("An error occurred", response.get_data(as_text=True))

    def test_valid_upload_returns_csv_report(self):
        response = self.post_files()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        disposition = response.headers["Content-Disposition"]
        self.assertRegex(
            disposition, r"Processed_Attendance_Report_\d{4}-\d{2}-\d{2}\.csv"
        )
        body = response.get_data(as_text=True)
        header = body.splitlines()[0]
        self.assertEqual(header, ",".join(["Last Name", "First Name"] + COLUMNS))
        self.assertIn("90:30", body)
        self.assertIn("2.5", body)

    def test_uploaded_files_are_deleted_after_processing(self):
        before = set(os.listdir(app.config["UPLOAD_FOLDER"]))
        self.post_files()  # success path
        self.post_files(weekly=("weekly.csv", b"Wrong\n1\n"))  # error path
        after = set(os.listdir(app.config["UPLOAD_FOLDER"]))
        self.assertEqual(before, after)

    def test_oversized_upload_is_rejected(self):
        big = b"a" * (app.config["MAX_CONTENT_LENGTH"] + 1)
        response = self.post_files(weekly=("weekly.csv", big))
        self.assertEqual(response.status_code, 413)


class PrivacyNoteTests(RouteTestCase):
    PAGES = ("/", "/instructions")

    def page(self, path):
        return self.client.get(path).get_data(as_text=True)

    def test_note_present_on_both_pages(self):
        for path in self.PAGES:
            with self.subTest(path=path):
                html = self.page(path)
                self.assertEqual(html.count('class="privacy-note"'), 1)
                self.assertIn("deleted immediately", html)
                self.assertIn("Google Analytics", html)

    def test_analytics_tag_matches_disclosure(self):
        # The disclosure is only accurate while the tag is the only tracker.
        for path in self.PAGES:
            with self.subTest(path=path):
                html = self.page(path)
                self.assertIn("googletagmanager.com/gtag/js", html)
                self.assertEqual(html.count("gtag('config'"), 1)
                self.assertNotIn("gtag('event'", html)

    def test_google_link_is_safe_and_correct(self):
        for path in self.PAGES:
            with self.subTest(path=path):
                match = re.search(r'<a href="(https://policies\.google\.com[^"]*)"([^>]*)>',
                                  self.page(path))
                self.assertIsNotNone(match)
                self.assertIn("noopener", match.group(2))
                self.assertIn("noreferrer", match.group(2))

    def test_note_sits_inside_the_card_container(self):
        # Regression: the note once rendered outside .container and landed
        # beside the card because <body> is a flex row.
        for path in self.PAGES:
            with self.subTest(path=path):
                html = self.page(path)
                container = html.index('<div class="container">')
                note = html.index('class="privacy-note"')
                scripts = html.index("<!-- Bootstrap JS")
                self.assertLess(container, note)
                self.assertLess(note, scripts)
                # Exactly one closing </div> (the container's) between the
                # note and the scripts, so the note is still inside it.
                tail = html[note:scripts]
                self.assertEqual(tail.count("</div>"), 1)
                self.assertEqual(tail.count("<div"), 0)

    def test_html_stays_well_formed_around_note(self):
        for path in self.PAGES:
            with self.subTest(path=path):
                html = self.page(path)
                self.assertEqual(html.count("<p class=\"privacy-note\""), 1)
                self.assertEqual(html.count("</body>"), 1)
                self.assertEqual(html.count("</html>"), 1)

    def test_note_does_not_appear_in_downloaded_report(self):
        response = self.post_files()
        self.assertNotIn("Google Analytics", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
