"""Offline tests of the image checks that keep broken images out of the slides."""

import io
import os

from PIL import Image, ImageOps

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


def test_a_big_jpeg_is_decoded_at_a_fraction_of_its_size_yet_comes_out_as_large(monkeypatch):
    # (as on talkgenerator.com, where Reddit's 24-megapixel originals pushed the server to its memory limit)
    shrunk_from = []
    thumbnail = Image.Image.thumbnail

    def spy(image, *args, **kwargs):
        shrunk_from.append(image.size)
        return thumbnail(image, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "thumbnail", spy)
    big = io.BytesIO()
    Image.new("L", (6000, 4000), 128).save(big, "JPEG")  # (as a 24-megapixel camera's, in gray to keep it light)
    converted = image_util.prepare_image_bytes(big.getvalue())
    assert shrunk_from == [(3000, 2000)]  # (decoded at half its size)
    assert image_util.get_image_size(converted) == (image_util.MAX_DIMENSION, 1600)


def test_a_phone_photo_is_decoded_at_half_its_size_still_wider_than_a_slide():
    phone = io.BytesIO()
    Image.new("L", (4032, 3024), 128).save(phone, "JPEG")  # (12 megapixels)
    converted = image_util.prepare_image_bytes(phone.getvalue())
    assert image_util.get_image_size(converted) == (2016, 1512)  # (more than the slides' 1920 pixels)


def test_a_photo_is_turned_as_its_camera_says_once_it_is_small(monkeypatch):
    turned = []
    exif_transpose = ImageOps.exif_transpose

    def spy(image, *args, **kwargs):
        turned.append(image.size)
        return exif_transpose(image, *args, **kwargs)

    monkeypatch.setattr(ImageOps, "exif_transpose", spy)
    exif = Image.Exif()
    exif[0x0112] = 6  # (orientation: the camera was turned a quarter clockwise)
    photo = io.BytesIO()
    Image.new("RGB", (4000, 1000), (20, 120, 200)).save(photo, "JPEG", exif=exif)
    converted = image_util.prepare_image_bytes(photo.getvalue())
    assert turned == [(2000, 500)]  # (decoded at half its size, still wider than a slide)
    assert image_util.get_image_size(converted) == (500, 2000)


def test_removed_image_placeholders_are_rejected():
    directory = os_util.to_actual_file("data/prohibited_images/")
    for file_name in os.listdir(directory):
        with open(os.path.join(directory, file_name), "rb") as file:
            assert image_util.prepare_image_bytes(file.read()) is None, file_name


def test_a_placeholder_is_recognised_at_a_larger_size_too():
    # (its fingerprint is taken from a reduced copy of a big image)
    directory = os_util.to_actual_file("data/prohibited_images/")
    for file_name in ("denied.jpg", "imgur_removed.jpg", "tinypic_removed2.jpg"):
        with Image.open(os.path.join(directory, file_name)) as placeholder:
            larger = placeholder.convert("RGB").resize((placeholder.width * 3, placeholder.height * 3))
        assert image_util.is_prohibited(larger), file_name
    assert not image_util.is_prohibited(Image.new("RGB", (900, 900), (20, 120, 200)))


def test_local_assets_are_used_as_is():
    path = os_util.to_actual_file("data/images/black-transparent.png")
    with open(path, "rb") as file:
        assert image_util.fetch_image(path) == file.read()


def test_formats_we_dont_need_are_never_parsed():
    # A valid TIFF, which Pillow would happily open, is refused: only common web formats get parsed
    tiff = _image_bytes(image_format="TIFF")
    with Image.open(io.BytesIO(tiff)) as image:
        assert image.format == "TIFF"
    assert image_util.prepare_image_bytes(tiff) is None
    assert "TIFF" not in image_util.accepted_formats()
    assert {"JPEG", "PNG", "GIF", "WEBP"} <= set(image_util.accepted_formats())
