from viewer import Ui_MainWindow
from PySide6 import QtCore, QtWidgets, QtGui
from pathlib import Path

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from enum import Enum, auto


@dataclass
class RenderElement:
    frame : int = 0
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
    end_time: datetime = 0.0
    start_time: datetime = 0.0
    exit_code: int = 0
    file_name: str = ""
    file_path: Path = None
    log_file: Path = None
    metric : str = ""
    status: str = ""
    stats: dict = field(default_factory=dict)
    worker_index: int = 0
    diff: dict = field(default_factory=dict) # dict of TestDiff objects mapping the name of the render element to the list of frames generated for this type of output

@dataclass
class TestHeader:
    total_tests: int = 0
    failed_tests: int = 0
    labels: list = field(default_factory=list)
    result_version: str = ""
    stats_fields: dict = field(default_factory=lambda: {
        "frameTime": { "label": "Frame Time", "dimension": "s"},
        "fullFrameTime": { "label": "Full Frame Time", "dimension": "s"},
        "totalTime": { "label": "Total Time", "dimension": "s"},
    })
    title: str = "Results"
    update_ref_times : bool = False
    version : dict = field(default_factory=dict)
    duration: timedelta = field(default_factory=timedelta)

def load_render_element(json_data, frame)-> RenderElement:
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
        diff.render_elements = [load_render_element(element, frame) for element in diff_item.get("renderElements", [])]
        diffs.append(diff)

    # create unique render elements by name
    render_elements = {}
    for diff in diffs:
        for element in diff.render_elements:
            if element.name not in render_elements:
                render_elements[element.name] = []
            render_elements[element.name].append(element)

    # sort render_elements by frame number
    for name, elements in render_elements.items():
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
    # result.diff = [load_test_diff(diff_item) for diff_item in json_data.get("diff", [])]
    result.diff = load_test_diff(json_data.get("diff", []))

    return result
    
def load_test_header(json_data) -> TestHeader:
    test_header = TestHeader()
    test_header.total_tests = json_data.get("allTestsCount", 0)
    test_header.failed_tests = json_data.get("failedTestsCount", 0)
    test_header.labels = json_data.get("labels", [])
    test_header.result_version = json_data.get("resultVersion", "3.0")
    test_header.stats_fields = json_data.get("statsFields", {
        "frameTime": { "label": "Frame Time", "dimension": "s"},
        "fullFrameTime": { "label": "Full Frame Time", "dimension": "s"},
        "totalTime": { "label": "Total Time", "dimension": "s"},
    })
    test_header.title = json_data.get("title", "Results")
    test_header.update_ref_times = json_data.get("updateRefTimes", False)
    test_header.version = json_data.get("version", {})
    # duration conversion
    duration_str = test_header.version.get("duration", "0:0:0")
    hours, minutes, seconds = map(int, duration_str.split(":"))
    test_header.duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    return test_header


def open_directory_dialog(default_folder: Path=None) -> Path:
    if default_folder:
        folder = default_folder
    else:
        options = QtWidgets.QFileDialog.Options()
        folder = QtWidgets.QFileDialog.getExistingDirectory(None, "Select Folder", "", options=options)
    return Path(folder) if folder else None

class TreeUserRole(Enum):
    Type = QtCore.Qt.UserRole
    Data = QtCore.Qt.UserRole + 1


class TreeItemType(Enum):
    Directory = auto()
    TestResult = auto()
    RenderElement = auto()

def set_table_model(view, model):
    view.setModel(model)
    header = view.horizontalHeader()
    header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)

def create_render_elements_table_model(data : RenderElement):
        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(["Field", "Value"])
        model.appendRow([QtGui.QStandardItem("Name"), QtGui.QStandardItem(data.name)])
        model.appendRow([QtGui.QStandardItem("Frame"), QtGui.QStandardItem(str(data.frame))])
        model.appendRow([QtGui.QStandardItem("Delta Count"), QtGui.QStandardItem(str(data.delta_count))])
        model.appendRow([QtGui.QStandardItem("Delta File"), QtGui.QStandardItem(str(data.delta_file))])
        model.appendRow([QtGui.QStandardItem("Status"), QtGui.QStandardItem(data.status)])
        model.appendRow([QtGui.QStandardItem("Exit Code"), QtGui.QStandardItem(str(data.exit_code))])        
        return model

def create_test_result_teable_model(data: TestResult):
        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(["Field", "Value"])
        model.appendRow([QtGui.QStandardItem("Name"), QtGui.QStandardItem(data.file_name)])
        model.appendRow([QtGui.QStandardItem("File Path"), QtGui.QStandardItem(str(data.file_path))])
        model.appendRow([QtGui.QStandardItem("Log File"), QtGui.QStandardItem(str(data.log_file))])
        model.appendRow([QtGui.QStandardItem("Exit Code"), QtGui.QStandardItem(str(data.exit_code))])
        model.appendRow([QtGui.QStandardItem("Status"), QtGui.QStandardItem(data.status)])
        model.appendRow([QtGui.QStandardItem("Metric"), QtGui.QStandardItem(data.metric)])
        model.appendRow([QtGui.QStandardItem("Worker Index"), QtGui.QStandardItem(str(data.worker_index))])
        model.appendRow([QtGui.QStandardItem("Start Time"), QtGui.QStandardItem(data.start_time.strftime("%Y-%m-%d %H:%M:%S"))])
        model.appendRow([QtGui.QStandardItem("End Time"), QtGui.QStandardItem(data.end_time.strftime("%Y-%m-%d %H:%M:%S"))])
        model.appendRow([QtGui.QStandardItem("Duration"), QtGui.QStandardItem(str(data.end_time - data.start_time))])
        return model

def create_pixmap_scaled(file, size):
        if file:
            return QtGui.QPixmap(str(file)).scaled(size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
        return None

def setup_label_size_policy(label: QtWidgets.QLabel, size_policy: QtWidgets.QSizePolicy):
    label.setSizePolicy(size_policy)
    label.setMinimumSize(10, 10)  # Small minimum size
    label.setScaledContents(True)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.ui = Ui_MainWindow()
        
        self.setGeometry(100, 100, 800, 600)
        self.ui.setupUi(self)
        self.setWindowTitle("VRay Results Viewer")

        # Set size policies for labels to allow them to shrink
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)
        setup_label_size_policy(self.ui.label_resultImage, size_policy)
        setup_label_size_policy(self.ui.label_diffImage, size_policy)
        setup_label_size_policy(self.ui.label_referenceImage, size_policy)
        
        self.current_frame = 0
        self.current_render_elements = None

        # for filtering the tree view
        self.proxy_model = QtCore.QSortFilterProxyModel(self)
        self.proxy_model.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.ui.lineEdit_searchBar.textChanged.connect(self.proxy_model.setFilterFixedString)
    
        self.cwd = Path.cwd()
        # not actually required, but for clarity
        self.results_json = None
        self.test_header = TestHeader()
        self.test_results = list[TestResult]

        self.ui.actionLoad.triggered.connect(self.load)
        self.ui.actionExit.triggered.connect(self.close)
        
        self.ui.treeView_results.clicked.connect(self.on_tree_view_clicked)
        self.ui.horizontalSlider_frames.valueChanged.connect(self.on_slider_valueChanged)
        self.load(Path("D:/Vray/hip_output"))
    
    def adjust_status_bar(self, min, max, step, value):
        self.ui.horizontalSlider_frames.setMinimum(min)
        self.ui.horizontalSlider_frames.setMaximum(max)
        self.ui.horizontalSlider_frames.setSingleStep(step)
        self.ui.horizontalSlider_frames.setValue(value)

    def resizeEvent(self, event: QtCore.QEvent):
        if hasattr(self, "current_render_elements") and self.current_render_elements:
            self.load_image()
        super().resizeEvent(event)
    
    def on_slider_valueChanged(self, value: int):
        self.current_frame = value
        if not self.current_render_elements:
            return
        if self.current_frame < 0 or self.current_frame >= len(self.current_render_elements):
            print("Invalid frame number")
            return
        self.load_image()
        self.load_render_elements_info()
    
    def load_image(self):
        render_element = self.current_render_elements[self.current_frame]
        self.ui.label_resultImage.setPixmap(create_pixmap_scaled(render_element.run_file, self.ui.label_resultImage.size()))
        self.ui.label_referenceImage.setPixmap(create_pixmap_scaled(render_element.run_file, self.ui.label_referenceImage.size()))
        self.ui.label_diffImage.setPixmap(create_pixmap_scaled(render_element.delta_file, self.ui.label_diffImage.size()))
    
    def load_render_elements_info(self):
        redner_element = self.current_render_elements[self.current_frame]
        model = create_render_elements_table_model(redner_element)
        set_table_model(self.ui.tableView_stats, model)
  
    def handle_stats_display(self, data: TestResult | RenderElement):
        if isinstance(data, TestResult):
            model = create_test_result_teable_model(data)
        elif isinstance(data, list):
            model = create_render_elements_table_model(data[self.current_frame])
        set_table_model(self.ui.tableView_stats, model)

    def handle_image_display(self, render_elements: list[RenderElement]):
        self.current_render_elements = render_elements
        self.load_image()    

    def on_tree_view_clicked(self, index: QtCore.QModelIndex):
        item = self.proxy_model.mapToSource(index)
        if not item.isValid():
            return
            
        type = item.data(TreeUserRole.Type.value)
        self.current_frame = 0

        if type == TreeItemType.TestResult.value:
            test_result = item.data(TreeUserRole.Data.value)
            key = next(iter(test_result.diff.keys()))
            print(f"Displaying: {key}")
            render_elements = test_result.diff[key]
            if render_elements:
                self.adjust_status_bar(0, len(render_elements)-1, 1, self.current_frame)
                self.handle_image_display(render_elements)
            self.handle_stats_display(test_result)
        elif type == TreeItemType.RenderElement.value:
            render_elements = item.data(TreeUserRole.Data.value)
            self.adjust_status_bar(0, len(render_elements)-1, 1, self.current_frame)
            self.handle_image_display(render_elements)
            self.handle_stats_display(render_elements)

    def load_json_results(self, json_results_file):
        print(f"Loading results from {json_results_file}")
        with open(json_results_file, 'r') as file:
            self.results_json = json.load(file)
        self.test_header = load_test_header(self.results_json)
        self.test_results = [load_test_result(test) for test in self.results_json.get("tests", [])]
        print(f"Loaded {len(self.test_results)} test results")

    def load(self, default_folder: Path=None):
        print("Loading results")
        folder = default_folder if default_folder else open_directory_dialog()
        if not folder:
            print("No results file found")
            return
        
        self.load_json_results(folder / "results.json")
        self.cwd = Path(folder)
        QtCore.QDir.setCurrent(str(self.cwd))
        self.populate_tree_view()

    def populate_tree_view(self):
        print("Populating tree view")
       
        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(["Results"])

        directory_items = {}

        for test_result in self.test_results:
            # Create a new item for each test result
            directory = test_result.file_path.parent
            if directory not in directory_items:
                directory_item = QtGui.QStandardItem(str(directory))
                directory_items[directory] = directory_item
                directory_item.setData(TreeItemType.Directory.value, TreeUserRole.Type.value)
                directory_item.setData(directory, TreeUserRole.Data.value)
                model.appendRow(directory_item)
            else:
                directory_item = directory_items[directory]
        
            test_item = QtGui.QStandardItem(test_result.file_name)
            test_item.setToolTip(f"Status: {test_result.status}\nMetric: {test_result.metric}\nExit Code: {test_result.exit_code}")
            test_item.setData(TreeItemType.TestResult.value, TreeUserRole.Type.value)
            test_item.setData(test_result, TreeUserRole.Data.value)
            # check the test_result exit code if it is not 0, set the background color to red
            if test_result.exit_code != 0:
                test_item.setBackground(QtGui.QBrush(QtGui.QColor(255, 0, 0, 100)))

            # check the test_result diff for the render elements
            for name, elements  in test_result.diff.items():
                n_frames = len(elements)
                item_name = name if n_frames == 1 else f"{name} (x{n_frames})"
                render_element = elements[0]
                render_element_item = QtGui.QStandardItem(item_name)
                render_element_item.setToolTip(f"Delta Count: {render_element.delta_count}\nStatus: {render_element.status}")
                render_element_item.setData(TreeItemType.RenderElement.value, TreeUserRole.Type.value)
                render_element_item.setData(elements, TreeUserRole.Data.value)
                if render_element.exit_code != 0:
                    render_element_item.setBackground(QtGui.QBrush(QtGui.QColor(255, 165, 0, 100)))
                else:
                    render_element_item.setBackground(QtGui.QBrush(QtGui.QColor(0, 255, 0, 100)))
                test_item.appendRow(render_element_item)
                    
            directory_item.appendRow(test_item)
        
        self.proxy_model.setSourceModel(model)
        self.ui.treeView_results.setModel(self.proxy_model)
        self.ui.treeView_results.expandAll()
        
    def close(self):
        print("Closing application")
        self.close()

if __name__ == "__main__":
    import sys
   
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())

