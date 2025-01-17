import os
import shutil
import platform
import subprocess

from qgis._core import QgsFeature, QgsGeometry, QgsPointXY
from qgis.core import QgsVectorLayer, QgsProject, Qgis, QgsRasterLayer
from qgis.gui import QgsMapToolEmitPoint
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QCheckBox, QDoubleSpinBox

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
GRD2STREAM_EXECUTABLE = os.path.join(PROJECT_DIR, "lib", "grd2stream")
OUTPUT_TXT_FILE = os.path.join(PROJECT_DIR, "bin", "streamline.txt")


def is_wsl_available():
    return shutil.which("wsl") is not None


class FlowlineModule:
    def __init__(self, iface):
        self.iface = iface
        self.selected_raster_1 = None
        self.selected_raster_2 = None
        self.coordinate = None
        self.map_tool = None

        self.backward_steps = False
        self.step_size = 200.0
        self.max_integration_time = None
        self.max_steps = None
        self.output_format = None

    def open_selection_dialog(self):
        dialog = SelectionDialog(self.iface)

        if dialog.exec_():
            self.selected_raster_1 = dialog.selected_raster_1
            self.selected_raster_2 = dialog.selected_raster_2

            self.backward_steps = dialog.backward_steps
            self.step_size = dialog.step_size
            self.max_integration_time = dialog.max_integration_time
            self.max_steps = dialog.max_steps
            self.output_format = dialog.output_format

            self.iface.messageBar().pushMessage(
                "Info",
                f"Selected rasters: {self.selected_raster_1.name()}, {self.selected_raster_2.name()}",
                level=Qgis.Info,
                duration=5
            )
            self.prompt_for_coordinate()

    def prompt_for_coordinate(self):
        if self.map_tool:
            try:
                self.map_tool.canvasClicked.disconnect(self.coordinate_selected)
            except Exception:
                pass
        self.map_tool = QgsMapToolEmitPoint(self.iface.mapCanvas())
        self.map_tool.canvasClicked.connect(self.coordinate_selected)
        self.iface.mapCanvas().setMapTool(self.map_tool)
        self.iface.messageBar().pushMessage(
            "Info",
            "Click on the map to select a coordinate for the grd2stream command.",
            level=Qgis.Info,
            duration=5
        )

    def coordinate_selected(self, point):
        self.coordinate = (point.x(), point.y())
        self.iface.mapCanvas().unsetMapTool(self.map_tool)
        self.map_tool = None
        self.iface.messageBar().pushMessage(
            "Info",
            f"Coordinate selected: {self.coordinate}.",
            level=Qgis.Info,
            duration=5
        )
        self.run_grd2stream()

    def run_grd2stream(self):
        try:
            system = platform.system()

            if not self.selected_raster_1 or not self.selected_raster_2:
                raise ValueError("Two raster layers must be selected.")
            if not self.coordinate:
                raise ValueError("A coordinate must be selected.")

            def convert_to_wsl_path(path):
                return path.replace("\\", "/").replace("C:", "/mnt/c")

            grd2stream_executable = GRD2STREAM_EXECUTABLE
            raster_path_1 = self.selected_raster_1.dataProvider().dataSourceUri()
            raster_path_2 = self.selected_raster_2.dataProvider().dataSourceUri()
            output_txt_file = OUTPUT_TXT_FILE

            if system == "Windows":
                if not is_wsl_available():
                    raise RuntimeError("WSL is not installed. Please install WSL to use this tool.")
                grd2stream_executable = convert_to_wsl_path(grd2stream_executable)
                raster_path_1 = convert_to_wsl_path(raster_path_1)
                raster_path_2 = convert_to_wsl_path(raster_path_2)
                output_txt_file = convert_to_wsl_path(output_txt_file)

            x, y = self.coordinate
            command = [
                "bash", "-c",
                f'echo "{x} {y}" | {grd2stream_executable} {raster_path_1} {raster_path_2}'
            ] if system != "Windows" else [
                "wsl", "bash", "-c",
                f'echo "{x} {y}" | {grd2stream_executable} {raster_path_1} {raster_path_2}'
            ]

            if self.backward_steps:
                command[-1] += " -b"
            if self.step_size:
                command[-1] += f" -d {self.step_size}"
            if self.max_integration_time:
                command[-1] += f" -T {self.max_integration_time}"
            if self.max_steps:
                command[-1] += f" -n {self.max_steps}"
            if self.output_format:
                command[-1] += f" {self.output_format}"

            command[-1] += f" > {output_txt_file}"
            print(f"Executing Command: {' '.join(command)}")

            startupinfo = None
            if system == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                startupinfo=startupinfo
            )

            if result.returncode != 0:
                raise RuntimeError(f"Command failed: {result.stderr}")

            if not os.path.exists(OUTPUT_TXT_FILE):
                raise RuntimeError("The grd2stream command did not produce an output file.")

            self.add_txt_as_layer()

            self.iface.messageBar().pushMessage(
                "Success",
                "grd2stream executed. Results loaded as a layer.",
                level=Qgis.Info,
                duration=5
            )

        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", f"Unexpected error: {e}", level=Qgis.Critical, duration=5
            )

    def add_txt_as_layer(self):
        try:
            attribute_names = []
            attribute_types = []
            features = []

            with open(OUTPUT_TXT_FILE, "r") as infile:
                for line in infile:
                    line = line.strip()

                    # Metadata
                    if line.startswith("# @N"):
                        # "name|id"
                        attribute_names = line[4:].split("|")
                    elif line.startswith("# @T"):
                        # "string|integer"
                        attribute_types = line[4:].split("|")
                    elif line.startswith("# @D"):
                        # "streamline 1"|1
                        attribute_values = line[4:].split("|")
                        attribute_values = [v.strip('"') if '"' in v else v for v in attribute_values]
                    elif line.startswith("#") or line.startswith(">") or not line:
                        continue
                    else:
                        parts = line.split()
                        if len(parts) >= 3:
                            x, y, z = map(float, parts[:3])
                            feature = QgsFeature()
                            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
                            if attribute_names and attribute_values:
                                feature.setAttributes(attribute_values)
                            features.append(feature)

            uri_fields = "&".join(
                f"field={name}:{'string' if t == 'string' else 'integer' if t == 'integer' else 'double'}"
                for name, t in zip(attribute_names, attribute_types)
            )
            uri = f"point?crs={QgsProject.instance().crs().authid()}&{uri_fields}"

            layer_name = "Streamline"
            layer = QgsVectorLayer(uri, layer_name, "memory")
            provider = layer.dataProvider()

            provider.addFeatures(features)

            if not layer.isValid():
                raise RuntimeError("Failed to load TXT as a vector layer.")

            QgsProject.instance().addMapLayer(layer)

            self.iface.messageBar().pushMessage(
                "Success", f"Layer '{layer_name}' successfully loaded.", level=Qgis.Info, duration=5
            )

        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", f"Failed to load TXT file as layer: {e}", level=Qgis.Critical, duration=5
            )

class SelectionDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("Select your GDAL grids (e.g., GMT, NetCDF, GTiFF, etc.)")
        self.setMinimumWidth(400)

        self.selected_raster_1 = None
        self.selected_raster_2 = None
        self.backward_steps = False
        self.step_size = 0.0  # Default step size
        self.max_integration_time = None
        self.max_steps = None
        self.output_format = None

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Select the 1st grid layer:"))
        self.layer_box_1 = QComboBox()
        layout.addWidget(self.layer_box_1)
        layout.addWidget(QLabel("Select the 2nd grid layer:"))
        self.layer_box_2 = QComboBox()
        layout.addWidget(self.layer_box_2)

        self.populate_layers()

        layout.addWidget(QLabel("Options:"))

        self.backward_checkbox = QCheckBox("Backward Steps (-b)")
        layout.addWidget(self.backward_checkbox)

        self.step_size_input = QDoubleSpinBox()
        self.step_size_input.setDecimals(3)
        self.step_size_input.setMinimum(0.0)
        self.step_size_input.setMaximum(float("inf"))
        self.step_size_input.setSingleStep(1.0)
        self.step_size_input.setValue(0.0)
        layout.addWidget(QLabel("Step Size (-d):"))
        layout.addWidget(self.step_size_input)

        self.max_time_input = QLineEdit()
        self.max_time_input.setPlaceholderText("Maximum Integration Time (default: none)")
        layout.addWidget(QLabel("Maximum Integration Time (-T):"))
        layout.addWidget(self.max_time_input)

        self.max_steps_input = QLineEdit()
        self.max_steps_input.setPlaceholderText("Maximum Number of Steps (default: 10000)")
        layout.addWidget(QLabel("Maximum Number of Steps (-n):"))
        layout.addWidget(self.max_steps_input)

        layout.addWidget(QLabel("Output Format:"))
        self.output_format_box = QComboBox()
        self.output_format_box.addItem("x y dist (default)", None)
        self.output_format_box.addItem("x y dist v_x v_y (-l)", "-l")
        self.output_format_box.addItem("x y dist v_x v_y time (-t)", "-t")
        layout.addWidget(self.output_format_box)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.ok_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

    def populate_layers(self):
        layers = QgsProject.instance().mapLayers().values()
        raster_layers = [layer for layer in layers if isinstance(layer, QgsRasterLayer)]
        for layer in raster_layers:
            self.layer_box_1.addItem(layer.name(), layer)
            self.layer_box_2.addItem(layer.name(), layer)

    def accept(self):
        index_1 = self.layer_box_1.currentIndex()
        index_2 = self.layer_box_2.currentIndex()

        self.selected_raster_1 = self.layer_box_1.itemData(index_1)
        self.selected_raster_2 = self.layer_box_2.itemData(index_2)

        if self.selected_raster_1 == self.selected_raster_2:
            self.iface.messageBar().pushMessage(
                "Error",
                "Please select two different grid layers.",
                level=Qgis.Critical,
                duration=5
            )
            return

        self.backward_steps = self.backward_checkbox.isChecked()
        self.step_size = self.step_size_input.value()
        self.max_integration_time = self.max_time_input.text() or None
        self.max_steps = self.max_steps_input.text() or None
        self.output_format = self.output_format_box.currentData()

        super().accept()
