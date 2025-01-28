# DWG Processing Tools
# Convert DWG files into PNG using ODA File Converter & Inkscape binaries 
import os, subprocess, xml.etree.ElementTree as etree, ezdxf 
from ezdxf.addons.drawing import Frontend, RenderContext, svg, layout, config

# Binary paths
ODA_EXE_PATH = r"src/modules/ODAFileConverter-v25.12.0/ODAFileConverter.exe"
INKSCAPE_EXE_PATH = "src/modules/Inkscape/bin/inkscape.exe"

def main(target_dir:str):
    from time import time
    lap_time = time()

    for file in list_files(target_dir, "dwg"):
      print(f"Processing : {file}")
      extract_png(file)
      
      mid_lap = time()
      print(f"Conversion of DWG to PNG complete in {round(mid_lap - lap_time, 0)}s")
      lap_time = time()

def list_files(dir:str, filetype:str=None) -> list:
    output = []
    for path in os.listdir(dir):
        cur_path = f"{dir}/{path}"

        if os.path.isdir(cur_path):
            sub = list_files(cur_path)
            output = [*output, *sub]
            
        else:
            output.append(cur_path)

    if filetype:
        return [i for i in output if i.endswith(filetype)]
     
    return output

def extract_png(input_file:str) -> bool:
    """
    Convert a DWG file to PNG format and store in the same directory 
    
    - prints step error & returns False if failure occurs
    - else returns True
    """
    # Convert DWG to DXF

    # 1. Split source dir & file name for binary config
    input_file = input_file.replace("\\", "/").split("/")
    working_dir = "/".join(input_file[:-1])
    input_file = input_file[-1]
    
    # 2. Set output formats
    output_version = "ACAD2018"
    output_format = "dxf"

    # 3. Binary will not run with an ODA exe path containing "/" characters
    oda_exe_path = ODA_EXE_PATH.replace("/", "\\")

    # 4. Binary subprocess requires int's as str
    recursive = True 
    audit = True

    recursive = "1" if recursive else "0"
    audit = "1" if audit else "0"

    # 5. Run conversion process
    try:
      subprocess.run(
        args=[oda_exe_path, working_dir, working_dir, output_version, output_format, recursive, audit, input_file], 
        shell=True
      )
    except Exception as e:
        print(f"DWG to DXF error : {e}") 
        return False

    # Convert dxf to svg

    try:
        # 1. create the render context
        doc = ezdxf.readfile(f"{working_dir}/{input_file.replace(".dwg", ".dxf")}")    
        msp = doc.modelspace()
        context = RenderContext(doc)
        
        # 2. create the backend & frontend contexts
        backend = svg.SVGBackend()
        cfg = config.Configuration(
            color_policy=config.ColorPolicy.MONOCHROME,
            text_policy=config.TextPolicy.FILLING,
            hatching_timeout=120,
        )
        frontend = Frontend(context, backend, cfg)
        frontend.draw_layout(msp)
        
        # 3. create page layout - width / height = 0 is auto
        page = layout.Page(
            width=0, 
            height=0, 
            units=layout.Units.mm, 
            margins=layout.Margins.all(10),
            max_width=1800,
        )
        # 4. get the SVG string
        svg_string = backend.get_string(
            page=page, 
            settings=layout.Settings(
                scale=4, 
                fit_page=True, 
                page_alignment=layout.PageAlignment.MIDDLE_CENTER, 
                crop_at_margins=True,
            ),
        )
    except Exception as e:
        print(f"DXF to SVG error : {e}") 
        return False
     
    # 5. Write the file to an svg directory located beside the source path
    output_path = f"{working_dir}/{input_file.replace(".dwg", ".svg")}"
    
    with open(output_path, "wt", encoding="utf8") as fp:
        fp.write(svg_string)

    # Convert SVG file to PNG with Inkscape
    
    # 1. Check file can be processed
    try:
        etree.parse(output_path)
    except Exception as e:
        print(f"SVG parsing error : {e}")
        return False
    
    # 2. Run Inkscape conversion call
    try:
        subprocess.check_call([INKSCAPE_EXE_PATH, '--export-type=png', output_path])
    except Exception as e:
        print(f"Inkscape binary error : {e}")
        return False

    # Clean up temp files

    # 1. remove dxf file
    os.remove(output_path.replace(".svg", ".dxf"))
    
    # 2. remove svg file from img dir
    os.remove(output_path)

    return True

if __name__ == "__main__":
    # CLI Entry Point 
    import sys
    args = sys.argv
    if len(args) == 2:
        main(args[1])
    else:
        print("Please provide the source path as the only CLI argument...")