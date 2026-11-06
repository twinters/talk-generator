"""Download the NLTK data talkgenerator uses.

talkgenerator also downloads missing NLTK data by itself on first run; this script is handy for
deployments that prepare everything up front.

Usage:
    python run_nltk_download.py                       # NLTK's default data folder
    python run_nltk_download.py --data-dir /srv/...   # a specific folder (then set NLTK_DATA to it)
"""

import argparse
import ssl

import nltk

# Keep in sync with talkgenerator.util.language_util.REQUIRED_NLTK_RESOURCES
CORPORA = ["punkt_tab", "averaged_perceptron_tagger_eng", "wordnet", "stopwords"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Download NLTK data for talkgenerator")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Target directory for NLTK data (default: NLTK's standard download folder)",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS certificate verification (only for machines with a broken certificate store)",
    )
    args = parser.parse_args()

    if args.insecure:
        ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001

    ok = all(nltk.download(corpus, download_dir=args.data_dir) for corpus in CORPORA)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
