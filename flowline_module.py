import os
import shutil
import platform
import subprocess

from osgeo import gdal
from osgeo_utils.auxiliary.util import get_pixel_size
from qgis._core import QgsFeature, QgsGeometry, QgsPointXY
from qgis.core import QgsVectorLayer, QgsProject, Qgis, QgsRasterLayer
from qgis.gui import QgsMapToolEmitPoint
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QCheckBox, QDoubleSpinBox

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
GRD2STREAM_EXECUTABLE = os.path.join(PROJECT_DIR, "lib", "grd2stream")
OUTPUT_TXT_FILE = os.path.join(PROJECT_DIR, "bin", "streamlines.txt")


def is_wsl_available():
    """Checks if WSL is installed on the system."""
    return shutil.which("wsl") is not None


class FlowlineModule:
    def __init__(self, iface):
        self.iface = iface
        self.selected_raster_1 = None
        self.selected_raster_2 = None
        self.coordinate = None
        self.map_tool = None

        # Class variables for dialog options
        self.backward_steps = False
        self.step_size = 200.0
        self.max_integration_time = None
        self.max_steps = None
        self.output_format = None

    def open_geotiff_selection_dialog(self):
        """Opens the dialog to select rasters and grd2stream options."""
        dialog = GeoTiffSelectionDialog(self.iface)
        if dialog.exec_():
            # Store selected rasters
            self.selected_raster_1 = dialog.selected_raster_1
            self.selected_raster_2 = dialog.selected_raster_2

            # Store dialog options in class variables
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
        """Prompts the user to click a coordinate on the map."""
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
        """Handles the coordinate selection."""
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
        """Executes the grd2stream command with stored options."""
        try:
            system = platform.system()

            # Validate rasters and coordinate
            if not self.selected_raster_1 or not self.selected_raster_2:
                raise ValueError("Two raster layers must be selected.")
            if not self.coordinate:
                raise ValueError("A coordinate must be selected.")

            # Convert paths for WSL if on Windows
            def convert_to_wsl_path(path):
                return path.replace("\\", "/").replace("C:", "/mnt/c")

            grd2stream_executable = GRD2STREAM_EXECUTABLE
            raster_path_1 = self.selected_raster_1.dataProvider().dataSourceUri()
            raster_path_2 = self.selected_raster_2.dataProvider().dataSourceUri()
            output_txt_file = OUTPUT_TXT_FILE

            if system == "Windows":
                if not is_wsl_available():
                    raise RuntimeError("WSL is not installed. Please install WSL to use this feature.")
                grd2stream_executable = convert_to_wsl_path(grd2stream_executable)
                raster_path_1 = convert_to_wsl_path(raster_path_1)
                raster_path_2 = convert_to_wsl_path(raster_path_2)
                output_txt_file = convert_to_wsl_path(output_txt_file)

            # Prepare the command
            x, y = self.coordinate
            command = [
                "bash", "-c",
                f'echo "{x} {y}" | {grd2stream_executable} {raster_path_1} {raster_path_2}'
            ] if system != "Windows" else [
                "wsl", "bash", "-c",
                f'echo "{x} {y}" | {grd2stream_executable} {raster_path_1} {raster_path_2}'
            ]

            # Add optional parameters
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

            # Append output redirection
            command[-1] += f" > {output_txt_file}"

            # Debugging: Print the command
            print(f"Executing Command: {' '.join(command)}")

            # Execute the command
            result = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False  # Avoid raising an exception automatically
            )

            # Check for errors
            if result.returncode != 0:
                raise RuntimeError(f"Command failed: {result.stderr}")

            # Verify output file creation
            if not os.path.exists(OUTPUT_TXT_FILE):
                raise RuntimeError("The grd2stream command did not produce an output file.")

            # Load the TXT file as a QGIS layer
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
        """Loads the TXT file as a vector layer in QGIS, using metadata for attributes."""
        try:
            # Initialize metadata variables
            attribute_names = []
            attribute_types = []
            features = []

            with open(OUTPUT_TXT_FILE, "r") as infile:
                for line in infile:
                    line = line.strip()

                    # Parse metadata lines
                    if line.startswith("# @N"):
                        # Extract attribute names (e.g., "name|id")
                        attribute_names = line[4:].split("|")
                    elif line.startswith("# @T"):
                        # Extract attribute types (e.g., "string|integer")
                        attribute_types = line[4:].split("|")
                    elif line.startswith("# @D"):
                        # Extract attribute values (e.g., '"streamline 1"|1')
                        attribute_values = line[4:].split("|")
                        attribute_values = [v.strip('"') if '"' in v else v for v in attribute_values]
                    elif line.startswith("#") or line.startswith(">") or not line:
                        # Skip other metadata or empty lines
                        continue
                    else:
                        # Parse feature geometry (x, y, z)
                        parts = line.split()
                        if len(parts) >= 3:
                            x, y, z = map(float, parts[:3])
                            feature = QgsFeature()
                            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))

                            # Set attributes for the feature
                            if attribute_names and attribute_values:
                                feature.setAttributes(attribute_values)
                            features.append(feature)

            # Dynamically construct the URI with attributes
            uri_fields = "&".join(
                f"field={name}:{'string' if t == 'string' else 'integer' if t == 'integer' else 'double'}"
                for name, t in zip(attribute_names, attribute_types)
            )
            uri = f"point?crs={QgsProject.instance().crs().authid()}&{uri_fields}"

            # Create the memory layer
            layer_name = "Streamlines"
            layer = QgsVectorLayer(uri, layer_name, "memory")
            provider = layer.dataProvider()

            # Add features to the layer
            provider.addFeatures(features)

            # Check if the layer is valid
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

class GeoTiffSelectionDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("Select GeoTIFF Files and grd2stream Options")
        self.setMinimumWidth(400)

        # Initialize attributes
        self.selected_raster_1 = None
        self.selected_raster_2 = None
        self.backward_steps = False
        self.step_size = 200.0
        self.max_integration_time = None
        self.max_steps = None
        self.output_format = None

        # Layout
        layout = QVBoxLayout()

        # GeoTIFF selection
        layout.addWidget(QLabel("Select the first GeoTIFF layer:"))
        self.layer_box_1 = QComboBox()
        layout.addWidget(self.layer_box_1)

        layout.addWidget(QLabel("Select the second GeoTIFF layer:"))
        self.layer_box_2 = QComboBox()
        layout.addWidget(self.layer_box_2)

        self.populate_layers()

        # Options
        layout.addWidget(QLabel("Options:"))

        # Backward steps
        self.backward_checkbox = QCheckBox("Backward Steps (-b)")
        layout.addWidget(self.backward_checkbox)

        # Step size
        self.step_size_input = QDoubleSpinBox()
        self.step_size_input.setDecimals(3)  # Allow decimals
        self.step_size_input.setSingleStep(1.0)  # Increment by 1
        self.step_size_input.setValue(200.0)  # Default value
        layout.addWidget(QLabel("Step Size (-d inc):"))
        layout.addWidget(self.step_size_input)

        # Maximum integration time
        self.max_time_input = QLineEdit()
        self.max_time_input.setPlaceholderText("Maximum Integration Time (-T maxtime)")
        layout.addWidget(QLabel("Maximum Integration Time:"))
        layout.addWidget(self.max_time_input)

        # Maximum steps
        self.max_steps_input = QLineEdit()
        self.max_steps_input.setPlaceholderText("Maximum Number of Steps (-n maxsteps)")
        layout.addWidget(QLabel("Maximum Number of Steps:"))
        layout.addWidget(self.max_steps_input)

        # Output format
        layout.addWidget(QLabel("Output Format:"))
        self.output_format_box = QComboBox()
        self.output_format_box.addItem("Default (x y dist)", None)
        self.output_format_box.addItem("x y dist v_x v_y (-l)", "-l")
        self.output_format_box.addItem("x y dist v_x v_y time (-t)", "-t")
        layout.addWidget(self.output_format_box)

        # Buttons
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.ok_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

    def populate_layers(self):
        """Populates the combo boxes with all loaded GeoTIFF layers."""
        layers = QgsProject.instance().mapLayers().values()
        raster_layers = [layer for layer in layers if isinstance(layer, QgsRasterLayer)]
        for layer in raster_layers:
            self.layer_box_1.addItem(layer.name(), layer)
            self.layer_box_2.addItem(layer.name(), layer)

    def accept(self):
        """Handles OK button click and dynamically adjusts the step size."""
        index_1 = self.layer_box_1.currentIndex()
        index_2 = self.layer_box_2.currentIndex()

        self.selected_raster_1 = self.layer_box_1.itemData(index_1)
        self.selected_raster_2 = self.layer_box_2.itemData(index_2)

        if self.selected_raster_1 == self.selected_raster_2:
            self.iface.messageBar().pushMessage(
                "Error",
                "Please select two different GeoTIFF layers.",
                level=Qgis.Critical,
                duration=5
            )
            return

        # Store options
        self.backward_steps = self.backward_checkbox.isChecked()
        self.step_size = self.step_size_input.value()
        self.max_integration_time = self.max_time_input.text() or None
        self.max_steps = self.max_steps_input.text() or None
        self.output_format = self.output_format_box.currentData()

        super().accept()
