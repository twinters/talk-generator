import sys

from talkgenerator import generator


def main(args):
    """Main run method for command line talk generation."""
    if getattr(args, "list", False):
        print(generator.describe_schemas())
        return
    presentations, slide_deck, output_file = generator.generate_presentation_using_cli_arguments(args)


def main_cli():
    # `talkgenerator check ...` checks generated talks; everything else is the command line that makes a talk
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        from talkgenerator.checks import benchmark

        sys.exit(benchmark.main(sys.argv[2:]))
    args = generator.get_argument_parser().parse_args()
    main(args)


if __name__ == "__main__":
    main_cli()
