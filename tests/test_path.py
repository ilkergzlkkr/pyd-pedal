import pathlib


def test_path():
    assert str(pathlib.Path("pedal/assets")) + "\\" == "pedal\\assets\\"
