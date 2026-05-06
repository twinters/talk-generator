# -*- coding: utf-8 -*-
"""NLTK corpus downloader.

Run on first install (and after corpus list changes) to populate the NLTK data
directory used by the talkgenerator library.

Usage:
    python run_nltk_download.py                       # default: ~/nltk_data
    python run_nltk_download.py --data-dir /srv/...   # for production deploys
"""

import argparse
import ssl
import nltk


CORPORA = ["punkt", "averaged_perceptron_tagger", "wordnet", "pros_cons", "reuters"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Download NLTK corpora for talkgenerator")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Target directory for NLTK data (default: NLTK's standard search path)",
    )
    args = parser.parse_args()

    try:
        ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
    except AttributeError:
        pass

    for corpus in CORPORA:
        nltk.download(corpus, download_dir=args.data_dir)


if __name__ == "__main__":
    main()
