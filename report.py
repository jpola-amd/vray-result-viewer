from pathlib import Path

import pandas as pd

from models import TestResult, ReportEntry, ProblemLevel
from metrics import compute_metrics


def generate_report(test_results: list[TestResult]) -> list[ReportEntry]:
    report = []

    for test_result in test_results:
        directory = str(test_result.file_path.parent)
        for name, elements in test_result.diff.items():
            for element in elements:
                metrics = compute_metrics(element.run_file, element.ref_file)
                if metrics:
                    report_entry = ReportEntry(
                        directory=directory,
                        test=test_result.file_name,
                        element=name,
                        mse=metrics.mse,
                        SSIM=metrics.ssim,
                        diff_percentage=(metrics.diff_pixels_count / metrics.total_pixels_count) * 100,
                        diff_count=metrics.diff_pixels_count,
                        diff_count_pre_computed=int(element.delta_count),
                        pixel_count=metrics.total_pixels_count,
                        problem_level=ProblemLevel.GOOD if metrics.ssim > 0.95 else ProblemLevel.SOFT,
                        level=int((metrics.diff_pixels_count / metrics.total_pixels_count) * 20),
                        message=element.status,
                    )
                else:
                    report_entry = ReportEntry(
                        directory=directory,
                        test=test_result.file_name,
                        element=name,
                        mse=0,
                        SSIM=0,
                        diff_percentage=0,
                        diff_count=0,
                        diff_count_pre_computed=int(element.delta_count),
                        pixel_count=0,
                        problem_level=ProblemLevel.HARD,
                        level=20,
                        message="Rendering failed",
                    )
                report.append(report_entry)

    return report


def report_to_dataframe(report: list[ReportEntry]) -> pd.DataFrame:
    df = pd.DataFrame([entry.__dict__ for entry in report])
    # convert ProblemLevel enum to string for clean CSV export
    df['problem_level'] = df['problem_level'].apply(lambda x: x.name)
    return df


def print_report_summary(report_df: pd.DataFrame):
    # remove emulation rows for summary
    df = report_df[report_df["directory"] != "emulation"]
    total_entries = len(df)
    if total_entries == 0:
        print("No entries to report")
        return

    print(f"Total entries: {total_entries}")
    print(df.describe())

    passed_tests = df[df['problem_level'] == 'GOOD']
    print(f"Passed tests: {len(passed_tests)}")
    print(passed_tests)

    soft_diff_tests = df[df['problem_level'] == 'SOFT']
    print(f"Soft diff tests: {len(soft_diff_tests)}")
    print(soft_diff_tests)

    high_diff_tests = df[df['diff_percentage'] > 50]
    print(f"High diff tests: {len(high_diff_tests)}")
    print(high_diff_tests)

    failed_tests_ratio = len(df[df['problem_level'] == 'HARD']) / total_entries
    print(f"Failed tests ratio: {failed_tests_ratio:.2%}")
    soft_diff_tests_ratio = len(df[df['problem_level'] == 'SOFT']) / total_entries
    print(f"Soft diff tests ratio: {soft_diff_tests_ratio:.2%}")
    passed_tests_ratio = len(df[df['problem_level'] == 'GOOD']) / total_entries
    print(f"Passed tests ratio: {passed_tests_ratio:.2%}")

    failed_tests = df[df['problem_level'] == 'HARD']
    print(f"Failed tests: {len(failed_tests)}")
    print(failed_tests)

    failed_tests_by_directory = df[df['problem_level'] == 'HARD'].groupby('directory').size()
    print(f"Failed tests by directory: {len(failed_tests_by_directory)}")
    print(failed_tests_by_directory)

    top_mse_tests = df.nlargest(5, 'mse')
    print(f"Top 5 tests by MSE: {len(top_mse_tests)}")
    print(top_mse_tests)
