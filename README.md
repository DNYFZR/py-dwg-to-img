<h2 align="center">DWG to PNG Converter</h2>

A small program for converting a DWG file to a PNG image & saving it in the same directory.

- The process will create a couple of temporary files in the directory, but they will be removed when the PNG has been saved.

- Sample data source : [ArcGIS](https://www.arcgis.com/home/item.html?id=1f4194190c5f435b8162bbf6b97aa341)

- Run [sync](/sync.py) to install project dependencies locally

- Testing requires Pytest (installed if sync is run)

- [External binaries](/src/modules) :

  - ODA File Converter : used to convert DWG to open DXF format
  - Inkscape : used to convert SVG to PNG format

### Run commands

Check [pyproject](/pyproject.toml) for system requirements

```ps1
# Setup local env
python -m venv .venv
./.venv/scripts/activate

# Install pyproject dependencies
python -m sync

# Run DWG conversion
python -m src.process_dwg "tests/data/CoL_WaterUtility_Sept25_2024.dwg"

```
