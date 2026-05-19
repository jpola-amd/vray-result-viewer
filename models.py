from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class RenderElement:
    frame: int = 0
    name: str = ""
    delta_count: int = 0
    status: str = ""
    exit_code: int = 0
    ref_file: Path = None
    ref_repro_file: Path = None
    run_file: Path = None
    delta_file: Path = None


@dataclass
class TestDiff:
    render_elements: list[RenderElement] = field(default_factory=list)


@dataclass
class TestResult:
    end_time: datetime = None
    start_time: datetime = None
    exit_code: int = 0
    file_name: str = ""
    file_path: Path = None
    log_file: Path = None
    metric: str = ""
    status: str = ""
    stats: dict = field(default_factory=dict)
    worker_index: int = 0
    # dict mapping render element name to list of frames
    diff: dict = field(default_factory=dict)


@dataclass
class TestHeader:
    total_tests: int = 0
    failed_tests: int = 0
    labels: list = field(default_factory=list)
    result_version: str = ""
    stats_fields: dict = field(default_factory=lambda: {
        "frameTime": {"label": "Frame Time", "dimension": "s"},
        "fullFrameTime": {"label": "Full Frame Time", "dimension": "s"},
        "totalTime": {"label": "Total Time", "dimension": "s"},
    })
    title: str = "Results"
    update_ref_times: bool = False
    version: dict = field(default_factory=dict)
    duration: timedelta = field(default_factory=timedelta)


class ProblemLevel(Enum):
    GOOD = auto()
    SOFT = auto()
    HARD = auto()


@dataclass
class ReportEntry:
    directory: str = ""
    test: str = ""
    element: str = ""
    mse: float = 0
    SSIM: float = 0
    diff_percentage: float = 0
    diff_count_pre_computed: int = 0
    diff_count: int = 0
    pixel_count: int = 0
    problem_level: ProblemLevel = ProblemLevel.HARD
    level: int = 0  # 20 levels every 5% of the diff count
    message: str = ""


@dataclass
class Metrics:
    total_pixels_count: int = 0
    diff_pixels_count: int = 0
    mse: float = 0
    ssim: float = 0
