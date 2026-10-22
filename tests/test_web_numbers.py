"""The website's numbers (web/src/numbers.ts) are generated from the results files, like docs/RESULTS.md."""

from eval import report


def test_web_numbers_match_the_results_files() -> None:
    assert report.WEB_NUMBERS.read_text(encoding="utf-8") == report.web_numbers(), "run python -m eval.report"
