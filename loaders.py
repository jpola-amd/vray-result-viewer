from pathlib import Path
from datetime import datetime, timedelta

from models import RenderElement, TestDiff, TestResult, TestHeader


def load_render_element(json_data, frame) -> RenderElement:
    render_element = RenderElement()
    render_element.frame = frame
    render_element.name = json_data.get("name", "")
    render_element.delta_count = json_data.get("deltaCount", 0)
    render_element.status = json_data.get("status", "")
    render_element.exit_code = json_data.get("exitCode", 0)
    render_element.ref_file = Path(json_data.get("refFile", ""))
    render_element.ref_repro_file = Path(json_data.get("refReproFile", ""))
    render_element.run_file = Path(json_data.get("runFile", ""))
    render_element.delta_file = Path(json_data.get("deltaFile", ""))
    return render_element


def load_test_diff(json_data) -> dict:
    diffs = []

    for diff_item in json_data:
        diff = TestDiff()
        frame = diff_item.get("frame", 0)
        diff.render_elements = [
            load_render_element(element, frame)
            for element in diff_item.get("renderElements", [])
        ]
        diffs.append(diff)

    # create unique render elements by name
    render_elements = {}
    for diff in diffs:
        for element in diff.render_elements:
            if element.name not in render_elements:
                render_elements[element.name] = []
            render_elements[element.name].append(element)

    # sort render_elements by frame number
    for _, elements in render_elements.items():
        elements.sort(key=lambda x: x.frame)

    return render_elements


def load_test_result(json_data) -> TestResult:
    result = TestResult()
    result.end_time = datetime.fromtimestamp(json_data.get("endTime", 0.0))
    result.start_time = datetime.fromtimestamp(json_data.get("startTime", 0.0))
    result.exit_code = json_data.get("exitCode", 0)
    result.file_name = json_data.get("fileName", "")
    result.file_path = Path(json_data.get("file", ""))
    result.log_file = Path(json_data.get("logFile", ""))
    result.metric = json_data.get("metric", "")
    result.status = json_data.get("status", "")
    result.stats = json_data.get("stats", {})
    result.worker_index = json_data.get("workerIndex", 0)
    result.diff = load_test_diff(json_data.get("diff", []))
    return result


def load_test_header(json_data) -> TestHeader:
    test_header = TestHeader()
    test_header.total_tests = json_data.get("allTestsCount", 0)
    test_header.failed_tests = json_data.get("failedTestsCount", 0)
    test_header.labels = json_data.get("labels", [])
    test_header.result_version = json_data.get("resultVersion", "3.0")
    test_header.stats_fields = json_data.get("statsFields", {
        "frameTime": {"label": "Frame Time", "dimension": "s"},
        "fullFrameTime": {"label": "Full Frame Time", "dimension": "s"},
        "totalTime": {"label": "Total Time", "dimension": "s"},
    })
    test_header.title = json_data.get("title", "Results")
    test_header.update_ref_times = json_data.get("updateRefTimes", False)
    test_header.version = json_data.get("version", {})
    # duration conversion
    duration_str = test_header.version.get("duration", "0:0:0")
    hours, minutes, seconds = map(int, duration_str.split(":"))
    test_header.duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    return test_header
