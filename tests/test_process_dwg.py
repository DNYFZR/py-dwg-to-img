import sys, pytest
sys.path.append("src")
from process_dwg import list_files, extract_png

TEST_DWG = "tests/data/CoL_WaterUtility_Sept25_2024.dwg"
TEST_PNG = "tests/data/CoL_WaterUtility_Sept25_2024.png"

@pytest.mark.parametrize(argnames="test_case", argvalues=[TEST_DWG])
def test_list_files(test_case):
    test_res = list_files("tests/data", ".dwg")
    
    if test_case not in test_res:
        raise AssertionError("List files test failed")

@pytest.mark.parametrize(argnames="test_case", argvalues=[TEST_PNG])
def test_process_dwg(test_case):
    extract_png(TEST_DWG)
    test_res = list_files("tests/data", ".png")

    if test_case not in test_res:
        raise AssertionError("Extract PNG test failed")
