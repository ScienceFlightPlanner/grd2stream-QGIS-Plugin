import os
import shutil
import platform
import subprocess

from qgis._core import QgsFeature, QgsGeometry, QgsPointXY
from qgis.core import QgsVectorLayer, QgsProject, Qgis, QgsRasterLayer
from qgis.gui import QgsMapToolEmitPoint
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QCheckBox, QDoubleSpinBox

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

    def install_miniconda(self):
        system = platform.system()
        conda_path = os.path.expanduser("~/miniconda3/bin/conda") if system in ["Linux", "Darwin"] else (
            os.path.expanduser("~/miniconda3/Scripts/conda.exe")
        )
        if os.path.exists(conda_path):
            print("Miniconda is already installed.")
            return
        print("Installing Miniconda...")
        if system == "Windows":
            command = (
                "wget \"https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe\" -outfile \".\\miniconda.exe\"; "
                "Start-Process -FilePath \".\\miniconda.exe\" -ArgumentList \"/S\" -Wait; "
                "del .\\miniconda.exe"
            )
            subprocess.run(["powershell", "-Command", command], check=True)
        elif system == "Darwin":
            command = (
                "mkdir -p ~/miniconda3 && "
                "curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-$(uname -m).sh -o ~/miniconda3/miniconda.sh && "
                "bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3 && "
                "rm ~/miniconda3/miniconda.sh"
            )
            subprocess.run(["bash", "-c", command], check=True)
        elif system == "Linux":
            command = (
                "mkdir -p ~/miniconda3 && "
                "wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh -O ~/miniconda3/miniconda.sh && "
                "bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3 && "
                "rm ~/miniconda3/miniconda.sh"
            )
            subprocess.run(["bash", "-c", command], check=True)
        print("Miniconda is now installed!")

    def setup_conda_environment(self):
        system = platform.system()
        conda_path = os.path.expanduser("~/miniconda3/bin/conda") if system in ["Linux", "Darwin"] else (
            os.path.expanduser("~/miniconda3/Scripts/conda.exe")
        )
        if not os.path.exists(conda_path):
            raise RuntimeError("Miniconda installation not found!")
        print("Setting up Conda environment...")
        if system in ["Linux", "Darwin"]:
            conda_path = os.path.expanduser("~/miniconda3/bin/conda")
            try:
                subprocess.run([conda_path, "config", "--add", "channels", "conda-forge"], check=True)
                subprocess.run([conda_path, "config", "--set", "channel_priority", "strict"], check=True)
                result = subprocess.run(
                    [conda_path, "create", "-y", "-n", "GMT6", "gmt=6*", "gdal", "hdf5", "netcdf4"], 
                    capture_output=True, text=True
                )
            except subprocess.CalledProcessError as e:
                print(f"Command failed with error: {e}")
            envs_output = subprocess.run([conda_path, "env", "list"], capture_output=True, text=True)
            if "GMT6" not in envs_output.stdout:
                self.iface.messageBar().pushMessage(
                    "Error", "GMT6 environment creation failed! Check logs.", level=Qgis.Critical, duration=5
                )
                print(f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}")
        elif system == "Windows":
            conda_commands = (
                "$env:Path = \"$env:USERPROFILE\\miniconda3\\Scripts;$env:USERPROFILE\\miniconda3\\Library\\bin;$env:Path\"; "
                "conda init powershell; "
                "conda config --add channels conda-forge; "
                "conda config --set channel_priority strict; "
                "conda create -y -n GMT6 gmt=6* gdal hdf5 netcdf4"
            )
            subprocess.run(["powershell", "-Command", conda_commands], check=True)
        print("Conda environment is now set up!")

    def install_grd2stream(self):
        system = platform.system()
        grd2stream_executable = os.path.expanduser("~/miniconda3/envs/GMT6/bin/grd2stream") \
            if system in ["Linux", "Darwin"] else os.path.expanduser("~/miniconda3/envs/GMT6/Library/bin/grd2stream.exe")
        if os.path.exists(grd2stream_executable):
            print("grd2stream is already installed!")
            return
        print("Installing grd2stream...")
        if system in ["Linux", "Darwin"]:
            conda_path = os.path.expanduser("~/miniconda3/bin/conda")
            download_grd2stream = "curl -fsSL https://github.com/tkleiner/grd2stream/releases/download/v0.2.14/grd2stream-0.2.14.tar.gz -o grd2stream-0.2.14.tar.gz"
            unzip_grd2stream = "tar xvfz grd2stream-0.2.14.tar.gz"
            navigate = "cd grd2stream-0.2.14"
            linker_flags = "export LDFLAGS=\"-Wl,-rpath,$CONDA_PREFIX/lib\""
            build_grd2stream = "./configure --prefix=\"$CONDA_PREFIX\" --enable-gmt-api"
            install_grd2stream = "make && make install"
            try:
                subprocess.run([conda_path, "activate", "GMT6"], check=True)
                subprocess.run(["bash", "-c", f"{download_grd2stream}"], check=True)
                subprocess.run(["bash", "-c", f"{unzip_grd2stream}"], check=True)
                subprocess.run(["bash", "-c", f"{navigate}"], check=True)
                subprocess.run(["bash", "-c", f"{linker_flags}"], check=True)
                subprocess.run(["bash", "-c", f"{build_grd2stream}"], check=True)
                subprocess.run(["bash", "-c", f"{install_grd2stream}"], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Command failed with error: {e}")
        elif system == "Windows":
            conda_init = (
                "$env:Path = \"$env:USERPROFILE\\miniconda3\\Scripts;$env:USERPROFILE\\miniconda3\\Library\\bin;$env:Path\"; "
                "conda activate GMT6"
            )
            build_commands = (
                f"{conda_init}; "
                "curl.exe -L https://github.com/tkleiner/grd2stream/releases/download/v0.2.14/grd2stream-0.2.14.tar.gz -o grd2stream-0.2.14.tar.gz; "
                "tar xvfz grd2stream-0.2.14.tar.gz; "
                "cd grd2stream-0.2.14; "
                "./configure --prefix=\"$env:CONDA_PREFIX\" --enable-gmt-api; "
                "make; "
                "make install"
            )
            subprocess.run(["powershell", "-Command", build_commands], check=True)
        print("grd2stream is now installed!")

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
            self.install_miniconda()
            self.setup_conda_environment()
            self.install_grd2stream()

            if not self.selected_raster_1 or not self.selected_raster_2:
                raise ValueError("Two raster layers must be selected.")
            if not self.coordinate:
                raise ValueError("A coordinate must be selected.")

            x, y = self.coordinate
            raster_path_1 = self.selected_raster_1.dataProvider().dataSourceUri()
            raster_path_2 = self.selected_raster_2.dataProvider().dataSourceUri()

            print("Running grd2stream...")

            grd2stream_executable = os.path.expanduser("~/miniconda3/envs/GMT6/bin/grd2stream") \
                if system in ["Linux", "Darwin"] else os.path.expanduser("~/miniconda3/envs/GMT6/Library/bin/grd2stream.exe")
            command = f'echo "{x} {y}" | {grd2stream_executable} "{raster_path_1}" "{raster_path_2}"'

            if self.backward_steps:
                command += " -b"
            if self.step_size:
                command += f" -d {self.step_size}"
            if self.max_integration_time:
                command += f" -T {self.max_integration_time}"
            if self.max_steps:
                command += f" -n {self.max_steps}"
            if self.output_format:
                command += f" {self.output_format}"

            print(f"Executing Command: {command}")

            result = subprocess.run(
                command,
                shell=True,
                executable="/bin/bash" if system in ["Linux", "Darwin"] else None,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )

            if result.returncode != 0:
                raise RuntimeError(f"Command failed: {result.stderr}")

            print("Raw Output:\n", result.stdout)
            self.load_streamline_from_output(result.stdout)

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

    def load_streamline_from_output(self, output):
        """Parses grd2stream output and loads it as a vector layer in QGIS."""
        try:
            features = []

            format_fields = {
                None: ["longitude", "latitude", "dist"],
                "-l": ["longitude", "latitude", "dist", "v_x", "v_y"],
                "-t": ["longitude", "latitude", "dist", "v_x", "v_y", "time"]
            }
            field_names = format_fields.get(self.output_format, ["longitude", "latitude", "dist"])

            for line in output.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith(">"):
                    continue

                parts = list(map(float, line.split()))
                if len(parts) < len(field_names):
                    continue

                x, y = parts[:2]
                attributes = parts

                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
                feature.setAttributes(attributes)
                features.append(feature)

            field_types = ["double"] * len(field_names)
            uri_fields = "&".join(f"field={name}:{ftype}" for name, ftype in zip(field_names, field_types))
            uri = f"point?crs={QgsProject.instance().crs().authid()}&{uri_fields}"

            layer_name = "Streamline"
            layer = QgsVectorLayer(uri, layer_name, "memory")
            provider = layer.dataProvider()
            provider.addFeatures(features)

            if not layer.isValid():
                raise RuntimeError("Failed to load output as a vector layer.")

            QgsProject.instance().addMapLayer(layer)

            self.iface.messageBar().pushMessage(
                "Success", f"Layer '{layer_name}' successfully loaded.", level=Qgis.Info, duration=5
            )

        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", f"Failed to load output as layer: {e}", level=Qgis.Critical, duration=5
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
        self.step_size_input.setDecimals(2)
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
