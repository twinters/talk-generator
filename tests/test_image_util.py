"""Offline tests of the image checks that keep broken images out of the slides."""

import io
import os

from PIL import Image

from talkgenerator.util import image_util, os_util


def _image_bytes(size=(400, 300), image_format="PNG", color=(200, 30, 30)):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, image_format)
    return output.getvalue()


def test_normal_image_is_kept_as_is():
    data = _image_bytes(image_format="JPEG")
    assert image_util.prepare_image_bytes(data) == data


def test_tiny_images_are_rejected():
    assert image_util.prepare_image_bytes(_image_bytes(size=(10, 10))) is None


def test_garbage_is_rejected():
    assert image_util.prepare_image_bytes(b"<html>Not found</html>") is None


def test_unsupported_format_is_converted():
    converted = image_util.prepare_image_bytes(_image_bytes(image_format="WEBP"))
    assert converted is not None
    with Image.open(io.BytesIO(converted)) as image:
        assert image.format in ("JPEG", "PNG")


def test_huge_images_are_scaled_down():
    converted = image_util.prepare_image_bytes(_image_bytes(size=(5000, 2000), image_format="PNG"))
    assert max(image_util.get_image_size(converted)) <= image_util.MAX_DIMENSION


def test_removed_image_placeholders_are_rejected():
    directory = os_util.to_actual_file("data/prohibited_images/")
    for file_name in os.listdir(directory):
        with open(os.path.join(directory, file_name), "rb") as file:
            assert image_util.prepare_image_bytes(file.read()) is None, file_name


def test_local_assets_are_used_as_is():
    path = os_util.to_actual_file("data/images/black-transparent.png")
    with open(path, "rb") as file:
        assert image_util.fetch_image(path) == file.read()
