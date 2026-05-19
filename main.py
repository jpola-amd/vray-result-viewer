from pathlib import Path
import sys
from enum import Enum, auto
import json

from PySide6 import QtCore, QtWidgets, QtGui
from viewer import Ui_MainWindow
from models import RenderElement, TestResult, TestHeader, ProblemLevel
from loaders import load_test_header, load_test_result
from report import generate_report, report_to_dataframe, print_report_summary


def open_directory_dialog(default_folder: Path = None) -> Path:
    if default_folder:
        folder = default_folder
    else:
        options = QtWidgets.QFileDialog.Options()
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            None, "Select folder with results", "", options=options
        )
    return Path(folder) if folder else None


class TreeUserRole(Enum):
    TYPE = QtCore.Qt.UserRole
    DATA = QtCore.Qt.UserRole + 1


class TreeItemType(Enum):
    DIRECTORY = auto()
    TEST_RESULT = auto()
    RENDER_ELEMENT = auto()


def set_table_model(view, model):
    view.setModel(model)
    header = view.horizontalHeader()
    header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)


def create_render_elements_table_model(data: RenderElement):
    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(["Field", "Value"])
    model.appendRow([QtGui.QStandardItem("Name"), QtGui.QStandardItem(data.name)])
    model.appendRow([QtGui.QStandardItem("Frame"), QtGui.QStandardItem(str(data.frame))])
    model.appendRow([QtGui.QStandardItem("Delta Count"), QtGui.QStandardItem(str(data.delta_count))])
    model.appendRow([QtGui.QStandardItem("Delta File"), QtGui.QStandardItem(str(data.delta_file))])
    model.appendRow([QtGui.QStandardItem("Status"), QtGui.QStandardItem(data.status)])
    model.appendRow([QtGui.QStandardItem("Exit Code"), QtGui.QStandardItem(str(data.exit_code))])
    return model


def create_test_result_table_model(data: TestResult):
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
        return QtGui.QPixmap(str(file)).scaled(
            size,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
    return None


def setup_label_size_policy(label: QtWidgets.QLabel, size_policy: QtWidgets.QSizePolicy):
    label.setSizePolicy(size_policy)
    label.setMinimumSize(10, 10)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.ui = Ui_MainWindow(self)

        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle("VRay Results Viewer")
        self.ui.treeView_results.installEventFilter(self)
        self.setAcceptDrops(True)

        # Set size policies for labels to allow them to shrink
        size_policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
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
        self.results_json = None
        self.test_header = TestHeader()
        self.test_results: list[TestResult] = []
        self.report = None
        self.report_df = None

        self.ui.actionLoad.triggered.connect(self.load)
        self.ui.actionExit.triggered.connect(self.close)
        self.ui.actionReport.triggered.connect(self.generate_report)

        self.ui.treeView_results.clicked.connect(self.on_tree_view_clicked)
        self.ui.horizontalSlider_frames.valueChanged.connect(self.on_slider_valueChanged)

        if len(sys.argv) > 1:
            folder = Path(sys.argv[1])
            if folder.is_dir():
                self.load(folder)
            else:
                print(f"Invalid folder: {folder}")

    # --- Drag & Drop ---

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = Path(urls[0].toLocalFile())
                if file_path.is_dir() or (file_path.is_file() and file_path.suffix.lower() == '.json'):
                    event.acceptProposedAction()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return

        file_path = Path(urls[0].toLocalFile())

        if file_path.is_dir():
            self.load(file_path)
        elif file_path.is_file() and file_path.suffix.lower() == '.json':
            try:
                self.cwd = file_path.parent
                QtCore.QDir.setCurrent(str(self.cwd))
                if self.load_json_results(file_path):
                    self.populate_tree_view()
            except (IOError, json.JSONDecodeError, ValueError) as e:
                print(f"Error loading JSON file: {e}")
        event.acceptProposedAction()

    # --- Event Handling ---

    def swap_run_with_ref_pixmap(self):
        run_pixmap = self.ui.label_resultImage.pixmap()
        ref_pixmap = self.ui.label_referenceImage.pixmap()
        self.ui.label_resultImage.setPixmap(ref_pixmap)
        self.ui.label_referenceImage.setPixmap(run_pixmap)

    def eventFilter(self, source: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if source == self.ui.treeView_results and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() == QtCore.Qt.Key.Key_Space:
                self.swap_run_with_ref_pixmap()
                return True
        return super().eventFilter(source, event)

    def adjust_status_bar(self, _min, _max, step, value):
        self.ui.horizontalSlider_frames.blockSignals(True)
        self.ui.horizontalSlider_frames.setMinimum(_min)
        self.ui.horizontalSlider_frames.setMaximum(_max)
        self.ui.horizontalSlider_frames.setSingleStep(step)
        self.ui.horizontalSlider_frames.setValue(value)
        self.ui.horizontalSlider_frames.blockSignals(False)

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

    # --- Image Display ---

    def load_image(self):
        render_element = self.current_render_elements[self.current_frame]
        self.ui.label_resultImage.setPixmap(create_pixmap_scaled(render_element.run_file, self.ui.label_resultImage.size()))
        self.ui.label_referenceImage.setPixmap(create_pixmap_scaled(render_element.ref_file, self.ui.label_referenceImage.size()))
        self.ui.label_diffImage.setPixmap(create_pixmap_scaled(render_element.delta_file, self.ui.label_diffImage.size()))

    def load_render_elements_info(self):
        render_element = self.current_render_elements[self.current_frame]
        model = create_render_elements_table_model(render_element)
        set_table_model(self.ui.tableView_stats, model)

    def handle_stats_display(self, data: TestResult | RenderElement):
        if isinstance(data, TestResult):
            model = create_test_result_table_model(data)
        elif isinstance(data, list):
            model = create_render_elements_table_model(data[self.current_frame])
        else:
            return
        set_table_model(self.ui.tableView_stats, model)

    def handle_image_display(self, render_elements: list[RenderElement]):
        self.current_render_elements = render_elements
        self.load_image()

    # --- Tree View ---

    def on_tree_selection_changed(self, selected, _):
        for index in selected.indexes():
            item = self.proxy_model.mapToSource(index)
            if not item.isValid():
                print("Invalid item selected")
                return
            item_type = item.data(TreeUserRole.TYPE.value)
            if item_type == TreeItemType.RENDER_ELEMENT.value:
                render_elements = item.data(TreeUserRole.DATA.value)
                self.adjust_status_bar(0, len(render_elements) - 1, 1, self.current_frame)
                self.handle_image_display(render_elements)
                self.handle_stats_display(render_elements)
            elif item_type == TreeItemType.TEST_RESULT.value:
                test_result = item.data(TreeUserRole.DATA.value)
                self.adjust_status_bar(0, len(test_result.diff) - 1, 1, self.current_frame)
                self.handle_stats_display(test_result)

    def on_tree_view_clicked(self, index: QtCore.QModelIndex):
        item = self.proxy_model.mapToSource(index)
        if not item.isValid():
            print("Invalid item clicked")
            return

        item_type = item.data(TreeUserRole.TYPE.value)
        self.current_frame = 0

        if item_type == TreeItemType.TEST_RESULT.value:
            test_result = item.data(TreeUserRole.DATA.value)
            self.handle_stats_display(test_result)
        elif item_type == TreeItemType.RENDER_ELEMENT.value:
            render_elements = item.data(TreeUserRole.DATA.value)
            self.adjust_status_bar(0, len(render_elements) - 1, 1, self.current_frame)
            self.handle_image_display(render_elements)
            self.handle_stats_display(render_elements)
        elif item_type == TreeItemType.DIRECTORY.value:
            data = item.data(TreeUserRole.DATA.value)
            print(f"Directory clicked: {data}")

    # --- Data Loading ---

    def load_json_results(self, json_results_file):
        print(f"Loading results from {json_results_file}")
        try:
            with open(json_results_file, 'r', encoding='utf-8') as file:
                self.results_json = json.load(file)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error reading results file: {e}")
            return False
        self.test_header = load_test_header(self.results_json)
        self.test_results = [load_test_result(test) for test in self.results_json.get("tests", [])]
        print(f"Loaded {len(self.test_results)} test results")
        return True

    def load(self, default_folder: Path = None):
        print("Loading results")
        folder = default_folder if default_folder else open_directory_dialog()
        if not folder:
            print("No results file found")
            return

        if not self.load_json_results(folder / "results.json"):
            return
        self.cwd = Path(folder)
        QtCore.QDir.setCurrent(str(self.cwd))
        self.populate_tree_view()

    def populate_tree_view(self):
        print("Populating tree view")

        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(["Results"])

        directory_items = {}

        for test_result in self.test_results:
            directory = test_result.file_path.parent
            if directory not in directory_items:
                directory_item = QtGui.QStandardItem(str(directory))
                directory_items[directory] = directory_item
                directory_item.setData(TreeItemType.DIRECTORY.value, TreeUserRole.TYPE.value)
                directory_item.setData(directory, TreeUserRole.DATA.value)
                model.appendRow(directory_item)
            else:
                directory_item = directory_items[directory]

            test_item = QtGui.QStandardItem(test_result.file_name)
            test_item.setToolTip(f"Status: {test_result.status}\nMetric: {test_result.metric}\nExit Code: {test_result.exit_code}")
            test_item.setData(TreeItemType.TEST_RESULT.value, TreeUserRole.TYPE.value)
            test_item.setData(test_result, TreeUserRole.DATA.value)
            if test_result.exit_code != 0:
                test_item.setBackground(QtGui.QBrush(QtGui.QColor(255, 0, 0, 100)))

            for name, elements in test_result.diff.items():
                n_frames = len(elements)
                item_name = name if n_frames == 1 else f"{name} (x{n_frames})"
                render_element = elements[0]
                render_element_item = QtGui.QStandardItem(item_name)
                render_element_item.setToolTip(f"Delta Count: {render_element.delta_count}\nStatus: {render_element.status}")
                render_element_item.setData(TreeItemType.RENDER_ELEMENT.value, TreeUserRole.TYPE.value)
                render_element_item.setData(elements, TreeUserRole.DATA.value)
                if render_element.exit_code != 0:
                    render_element_item.setBackground(QtGui.QBrush(QtGui.QColor(255, 165, 0, 100)))
                else:
                    render_element_item.setBackground(QtGui.QBrush(QtGui.QColor(0, 255, 0, 100)))
                test_item.appendRow(render_element_item)

            directory_item.appendRow(test_item)

        self.proxy_model.setSourceModel(model)
        self.ui.treeView_results.setModel(self.proxy_model)
        self.ui.treeView_results.expandAll()
        self.ui.treeView_results.selectionModel().selectionChanged.connect(self.on_tree_selection_changed)

    # --- Report ---

    def generate_report(self):
        if self.report:
            print("Report already generated")
            return

        self.report = generate_report(self.test_results)
        self.report_df = report_to_dataframe(self.report)
        print_report_summary(self.report_df)

        report_file = self.cwd / "report.csv"
        self.report_df.to_csv(report_file, index=False)
        print(f"Report saved to {report_file}")

    # --- Clear / Close ---

    def clear(self):
        print("Clearing application state")

        self.results_json = None
        self.test_header = TestHeader()
        self.test_results = []
        self.report = None
        self.report_df = None

        self.current_render_elements = None
        self.current_frame = 0

        self.ui.label_resultImage.clear()
        self.ui.label_referenceImage.clear()
        self.ui.label_diffImage.clear()

        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(["Results"])
        self.proxy_model.setSourceModel(model)
        self.ui.treeView_results.setModel(self.proxy_model)

        empty_model = QtGui.QStandardItemModel()
        empty_model.setHorizontalHeaderLabels(["Field", "Value"])
        set_table_model(self.ui.tableView_stats, empty_model)

        self.adjust_status_bar(0, 0, 1, 0)
        self.setWindowTitle("VRay Results Viewer")

        self.cwd = Path.cwd()
        QtCore.QDir.setCurrent(str(self.cwd))

    def close(self):
        print("Closing application")
        super().close()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
