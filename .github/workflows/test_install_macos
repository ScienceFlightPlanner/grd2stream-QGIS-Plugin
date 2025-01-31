import os
import subprocess
import sys

def run_command(command, shell=False):
    result = subprocess.run(command, shell=shell, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout

def install_miniconda():
    miniconda_path = os.path.expanduser("~/miniconda3")
    miniforge_installer = f"{miniconda_path}/miniconda.sh"
    os.makedirs(miniconda_path, exist_ok=True)
    print("Downloading Miniforge...")
    run_command([
        "curl", "-fsSL",
        "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh",
        "-o", miniforge_installer
    ])
    print("Installing Miniconda...")
    run_command(["bash", miniforge_installer, "-b", "-u", "-p", miniconda_path], shell=True)
    print("Removing installer...")
    os.remove(miniforge_installer)
    return miniconda_path

def setup_conda_environment(miniconda_path):
    conda_bin = os.path.join(miniconda_path, "bin", "conda")
    shell_setup = f"source {miniconda_path}/etc/profile.d/conda.sh"
    print("Configuring Conda...")
    run_command(f"{shell_setup} && {conda_bin} config --add channels conda-forge", shell=True)
    run_command(f"{shell_setup} && {conda_bin} config --set channel_priority strict", shell=True)
    print("Creating Conda environment 'GMT6'...")
    run_command(f"{shell_setup} && {conda_bin} create -y -n GMT6 gmt=6* gdal hdf5 netcdf4", shell=True)

def install_grd2stream(miniconda_path):
    shell_setup = f"source {miniconda_path}/etc/profile.d/conda.sh && conda activate GMT6"
    version = "0.2.14"
    archive_name = f"grd2stream-{version}.tar.gz"
    download_url = f"https://github.com/tkleiner/grd2stream/releases/download/v{version}/{archive_name}"
    print(f"Downloading grd2stream {version}...")
    run_command(f"{shell_setup} && curl -fsSL {download_url} -o {archive_name}", shell=True)
    print("Extracting package...")
    run_command(f"{shell_setup} && tar xvfz {archive_name}", shell=True)
    print("Building and installing grd2stream...")
    os.chdir(f"grd2stream-{version}")
    run_command(f"{shell_setup} && export LDFLAGS='-Wl,-rpath,$CONDA_PREFIX/lib' && ./configure --prefix=$CONDA_PREFIX --enable-gmt-api", shell=True)
    run_command(f"{shell_setup} && make && make install", shell=True)
    print("Installation complete.")

def verify_grd2stream(miniconda_path):
    shell_setup = f"source {miniconda_path}/etc/profile.d/conda.sh && conda activate GMT6"
    print("Verifying installation...")
    run_command(f"{shell_setup} && grd2stream -h", shell=True)
    print("grd2stream is installated!")

if __name__ == "__main__":
    miniconda_path = install_miniconda()
    setup_conda_environment(miniconda_path)
    install_grd2stream(miniconda_path)
    verify_grd2stream(miniconda_path)
