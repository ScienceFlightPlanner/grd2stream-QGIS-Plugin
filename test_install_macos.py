import os
import platform
import subprocess
import sys

class Grd2StreamInstaller:
    def __init__(self):
        self.system = platform.system()
        self.miniconda_path = os.path.expanduser("~/miniconda3")
        self.conda_bin = os.path.join(self.miniconda_path, "bin", "conda")

    def install_miniconda(self):
        if os.path.exists(self.conda_bin):
            print("Miniconda is already installed.")
            return
        print("Installing Miniconda...")
        command = (
            f"mkdir -p {self.miniconda_path} && "
            f"curl -fsSL https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-$(uname -m).sh -o {self.miniconda_path}/miniconda.sh && "
            f"bash {self.miniconda_path}/miniconda.sh -b -u -p {self.miniconda_path} && "
            f"rm {self.miniconda_path}/miniconda.sh"
        )
        subprocess.run(["bash", "-c", command], check=True)
        print("Miniconda is now installed!")

    def setup_conda_environment(self):
        if not os.path.exists(self.conda_bin):
            raise RuntimeError("Miniconda installation not found!")
        print("Setting up Conda environment...")
        try:
            subprocess.run([self.conda_bin, "config", "--add", "channels", "conda-forge"], check=True)
            subprocess.run([self.conda_bin, "config", "--set", "channel_priority", "strict"], check=True)
            result = subprocess.run(
                [self.conda_bin, "create", "-y", "-n", "GMT6", "gmt=6*", "gdal", "hdf5", "netcdf4"], 
                capture_output=True, text=True
            )
            envs_output = subprocess.run([self.conda_bin, "env", "list"], capture_output=True, text=True)
            if "GMT6" not in envs_output.stdout:
                print(f"GMT6 environment creation failed! Check logs.")
                print(f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"Error setting up Conda environment: {e}")
        print("Conda environment 'GMT6' is now set up!")

    def install_grd2stream(self):
        conda_activate = f"source {self.miniconda_path}/etc/profile.d/conda.sh && conda activate GMT6"
        grd2stream_executable = os.path.join(self.miniconda_path, "envs/GMT6/bin/grd2stream")
        if os.path.exists(grd2stream_executable):
            print("grd2stream is already installed!")
            return
        print("Installing grd2stream...")
        try:
            commands = [
                f"{conda_activate} && curl -fsSL https://github.com/tkleiner/grd2stream/releases/download/v0.2.14/grd2stream-0.2.14.tar.gz -o grd2stream-0.2.14.tar.gz",
                f"{conda_activate} && tar xvfz grd2stream-0.2.14.tar.gz",
                f"{conda_activate} && cd grd2stream-0.2.14 && export LDFLAGS=\"-Wl,-rpath,$CONDA_PREFIX/lib\"",
                f"{conda_activate} && cd grd2stream-0.2.14 && ./configure --prefix=\"$CONDA_PREFIX\" --enable-gmt-api",
                f"{conda_activate} && cd grd2stream-0.2.14 && make && make install"
            ]
            for cmd in commands:
                subprocess.run(["bash", "-c", cmd], check=True)
            gmt_lib_path = os.path.join(self.miniconda_path, "envs/GMT6/lib")
            grd2stream_executable = os.path.join(self.miniconda_path, "envs/GMT6/bin/grd2stream")
            subprocess.run(["install_name_tool", "-add_rpath", gmt_lib_path, grd2stream_executable], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Installation failed: {e}")
            sys.exit(1)
        print("grd2stream is now installed!")

    def verify_installation(self):
        conda_activate = f"source {self.miniconda_path}/etc/profile.d/conda.sh && conda activate GMT6"
        grd2stream_path = os.path.join(self.miniconda_path, "envs/GMT6/bin/grd2stream")
        gmt_lib_path = os.path.join(self.miniconda_path, "envs/GMT6/lib")
        try:
            print(f"Checking if grd2stream exists at {grd2stream_path}...")
            if not os.path.exists(grd2stream_path):
                print("grd2stream not found in expected path!")
                sys.exit(1)
            env = os.environ.copy()
            env["DYLD_LIBRARY_PATH"] = gmt_lib_path
            print("Running grd2stream -h...")
            subprocess.run(["bash", "-c", f"{conda_activate} && {grd2stream_path} -h"], check=True, env=env)
            print("grd2stream installation verified successfully!")
        except subprocess.CalledProcessError:
            print("grd2stream verification failed! Debug logs above.")
            sys.exit(1)

    def run(self):
        self.install_miniconda()
        self.setup_conda_environment()
        self.install_grd2stream()
        self.verify_installation()

if __name__ == "__main__":
    installer = Grd2StreamInstaller()
    installer.run()
