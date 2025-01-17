# grd2stream

## Description
The `grd2stream` QGIS plugin computes and displays streamlines based on velocity grids. This plugin requires **GMT (Generic Mapping Tools)** for core functionality. For compatibility with all GDAL file formats (e.g., NetCDF, GTiFF, etc.), ensure GMT version 6 is installed.

---

## Requirements for Full Functionality

### Windows & macOS
- **Install GMT from [GMT Releases](https://github.com/GenericMappingTools/gmt/releases).**
   - Ensure GMT version 6 is installed.

### Linux
Ubuntu/Debian:
```bash
sudo apt install gmtsudo pacman -S gmt
```
Arch/Manjaro:
```bash
sudo pacman -S gmt
```

---

## Troubleshooting
- If you encounter errors related to file format compatibility, ensure:
  - **GDAL** is installed (`pip install gdal`)
    - And sometimes `pip install pygmt` also does the trick
- For detailed logs, check the QGIS Python console!

---

## Authors
- [**Thomas Kleiner**](https://github.com/tkleiner)
- [**ScienceFlightPlanner**](https://github.com/ScienceFlightPlanner)

---

## Third-Party Licenses
This plugin includes the following third-party components:
- **grd2stream**:
   - A tool for computing flowlines from gridded velocity fields.
   - Licensed under the BSD 3-Clause License.
   - See the full [LICENSE](./libs/grd2stream/LICENSE.txt) text for details.
