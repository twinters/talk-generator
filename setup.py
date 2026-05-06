from os import listdir
from os.path import isfile, join

from setuptools import setup
from setuptools import find_packages

# Build a list of text-templates to install
DATA_PATH = "talkgenerator/data/"
text_templates_path = DATA_PATH + "text-templates/"
text_template_files = [
    f for f in listdir(text_templates_path) if isfile(join(text_templates_path, f))
]
all_text_templates = []
for f in text_template_files:
    all_text_templates.append(text_templates_path + f)


prohibited_images_path = DATA_PATH + "prohibited_images/"
prohibited_images_files = [
    f
    for f in listdir(prohibited_images_path)
    if isfile(join(prohibited_images_path, f))
]
prohibited_images = []
for f in prohibited_images_files:
    prohibited_images.append(prohibited_images_path + f)

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name="talkgenerator",
    version="3.1.0",
    description="Automatically generating presentation slide decks based on a given topic for improvised presentations",
    long_description="Check our GitHub repository on https://github.com/twinters/talk-generator for more information!",
    author="Thomas Winters, Kory Mathewson",
    author_email="info@thomaswinters.be",
    url="https://github.com/twinters/talk-generator",
    license="MIT License",
    python_requires=">=3.10",
    packages=find_packages(),
    package_dir={"talkgenerator": "talkgenerator"},
    data_files=[
        ("images", [DATA_PATH + "images/black-transparent.png"]),
        ("images", [DATA_PATH + "images/error_placeholder.png"]),
        ("powerpoint", [DATA_PATH + "powerpoint/template.pptx"]),
        ("prohibited_images", prohibited_images),
        ("text-templates", all_text_templates),
    ],
    include_package_data=True,
    install_requires=required,
    entry_points={"console_scripts": ["talkgenerator = talkgenerator.run:main_cli"]},
)
