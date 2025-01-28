# SPDX-FileCopyrightText: 2023 Software Freedom Conservancy <info@sfconservancy.org>
# SPDX-FileCopyrightText: 2024 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Script to extract afdesign data.

poetry run python -m inkaf.extract file.afdesign ...

Stores full extracted data in *.afdesign.json

"""

from io import BytesIO
import os
import json
import argparse
from pathlib import Path
import shutil
import traceback
import sys
from typing import Any, Dict

from inkaf.afinput import parse
from inkaf.svg.convert import AFConverter

HERE = os.path.dirname(__file__) or "."
# This is suggested by https://docs.python-guide.org/writing/structure/.
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from inkaf.parser.parse import AFParser  # noqa: E402
from inkaf.parser.json_encoder import EnhancedJSONEncoder  # noqa: E402
from inkaf.parser.types import AFObject  # noqa: E402
from inkaf.parser.extract import AFExtractor, FATFile, FATFileType, NormalFATFile  # noqa: E402
from inkaf.parser.consts import content_magic  # noqa: E402

EXTRACTION_ENDING = ".json"

parser = argparse.ArgumentParser(
    prog="poetry run python3 -m inkaf.extract",
    description="Inkscape AI extraction tool: Unzips and additionally extracts (preprocessed) parts of the passed AI files.",
)

parser.add_argument("filename", nargs="*", help="One or more afdesign files")
parser.add_argument(
    "-n", "--if-newer", action="store_true", help="Only re-extract files if newer"
)
parser.add_argument(
    "-v", "--verbose", action="store_true", help="verbose output on errors"
)
parser.add_argument(
    "-z", "--extract-full", action="store_true", help="extract entire archive"
)
parser.add_argument(
    "-c",
    "--collect-unit-tests",
    action="store_true",
    help="Collect unit tests. Modify the wrapper function to decide what to collect",
)


args = parser.parse_args()

typetests: Dict[Any, Any] = {}


def create_type_test():
    # We monkey-patch the parser to extract unit test data.

    _load_field = AFParser.load_field

    def new_load_field(self: AFParser, type_, array):
        start = self.get_pos()
        result = _load_field(self, type_, array)
        end = self.get_pos()

        type_ = type_ + (128 if array else 0)
        do = False

        if isinstance(result, AFObject) and result.get_type() in (
            "BGrd",
            "GRAY",
        ):
            do = True

        if do:
            self.data.stream.seek(start - 5)
            data = self.data.stream.read(end - start + 5)
            typetests[result.get_type()] = (data, result)

        return result

    AFParser.load_field = new_load_field  # type: ignore


if args.collect_unit_tests:
    create_type_test()


def process_fat_file(extractor: AFExtractor, fat_dir: Path, file: FATFile):
    if isinstance(file, NormalFATFile) and file.flag == FATFileType.NORMAL_WITH_NAME:
        try:
            data = extractor.extract(file)
        except Exception as e:
            print(
                f"\tbroken extraction: {traceback.format_exc() if args.verbose else e}"
            )
            return True
        # Store the .dat
        assert file.name is not None
        target = fat_dir / (file.name + ".dat")
        target.parent.mkdir(exist_ok=True)
        with open(target, "wb") as wf:
            wf.write(data)
        if data.startswith((content_magic).to_bytes(4, byteorder="little")):
            # Try to extract the json
            try:
                parsed = AFParser(BytesIO(data)).parse()
                with open(fat_dir / (file.name + ".json"), "w") as f:
                    json.dump(parsed, f, cls=EnhancedJSONEncoder, indent=4)
                print(
                    f"\t{file.name}: Parsed content written to {fat_dir / (file.name +'.json')}"
                )
            except Exception as e:
                print(
                    f"\tbroken binary parsing: {traceback.format_exc() if args.verbose else e}"
                )
                return True
    return False


def extract(file_name: Path, write_archive=args.extract_full) -> AFExtractor:
    stream = open(file_name, "rb")
    error = False
    extractor = AFExtractor(stream)
    assert extractor.content is not None

    print("\tFile version", extractor.content.header.version)
    print("\tFile Access Tables: ", len(extractor.fats), extractor.fats)

    if write_archive:
        archive_folder = file_name.parent / file_name.stem
        if archive_folder.exists():
            shutil.rmtree(archive_folder)
        for fat in extractor.fats:
            fat_dir = archive_folder / str(fat.creation_date).replace(":", "_")
            fat_dir.mkdir(parents=True, exist_ok=True)
            for file in fat.files:
                e = process_fat_file(extractor, fat_dir, file)
                error = e or error
    if error:
        raise ValueError("One or more errors occurred during extraction")
    return extractor


def process_file(file_name):
    if file_name.suffix != ".afdesign":
        return False, False

    print("Found file:", file_name)
    output_file_name = file_name.with_suffix(".afdesign" + EXTRACTION_ENDING)
    if output_file_name.exists() and args.if_newer:
        if file_name.stat().st_mtime > output_file_name.stat().st_mtime:
            print(f"\t{output_file_name} is old, replace")
        else:
            print(
                f"\tskip: {output_file_name} exists and is newer than original document."
            )
            return False, False
    try:
        extractor = extract(file_name)
        result = process_fat_file(
            extractor, file_name.parent, extractor.get_head_revision("doc.dat")
        )
        if result:
            return True, True

        print(f"\tnew: {output_file_name}")

    except Exception as e:
        print(f"\tbroken extraction: {traceback.format_exc() if args.verbose else e}")
        print("\tfail:", file_name)
        return True, True

    try:
        with open(file_name, "rb") as stream:
            converter = AFConverter(parse(stream))
            converter.convert()
            res = converter.doc.getroot().tostring()
            newfile = file_name.with_suffix(".svg")
            # print(res)
            if res != "":
                with open(newfile, "w") as f:
                    f.write(res.decode())

            print(f"\tWrote parsed document to {newfile}")
    except Exception as e:
        print(f"\tbroken conversion: {traceback.format_exc() if args.verbose else e}")
        print("\tfail:", file_name)
        return True, True

    return False, True


def main(files=args.filename):
    """Extract the files."""

    did_something = False
    error = False
    broken = []

    def _process(path):
        e_, d_ = process_file(path)

        if e_:
            broken.append(path)
        return did_something or d_, error or e_, broken

    for file_name in map(Path, files):
        if file_name.is_dir():
            print(os.listdir(file_name))
            for fn in os.listdir(file_name):
                did_something, error, broken = _process(file_name / fn)
        else:
            did_something, error, broken = _process(file_name)

    if not did_something:
        print("Nothing to do!")
    if error:
        print(
            "We could not process at least one file. Isolate the problem and create a unit test."
        )
        print("Broken files:\n\t", "\n\t".join(map(str, broken)))
    if args.collect_unit_tests:
        print(
            "\n".join(
                str(typetests[key]) + f", #{key}" for key in sorted(typetests.keys())
            )
        )

        print("Located:", sorted(set(typetests.keys())))
    return int(error)


if __name__ == "__main__":
    exit(main())
