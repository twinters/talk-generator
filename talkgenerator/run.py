import sys

from talkgenerator import generator

MCP_MISSING = (
    "talkgenerator mcp needs the MCP SDK: pip install 'talkgenerator[mcp]'. (On Windows on Arm, install it in an x64 "
    "Python: the SDK needs the cryptography package, which has no wheels for Windows on Arm.)"
)


def main(args):
    """Main run method for command line talk generation."""
    if getattr(args, "list", False):
        print(generator.describe_schemas())
        return
    presentations, slide_deck, output_file = generator.generate_presentation_using_cli_arguments(args)


def main_cli():
    # `talkgenerator check ...` checks generated talks; `render`, `schema` and `formats` are for talks planned
    # elsewhere (by Claude, through the Skill); `mcp` serves them as an MCP server; `login` and `logout` sign in to
    # OpenRouter; everything else is the command line that makes a talk
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        sys.exit(_mcp(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        from talkgenerator.checks import benchmark

        sys.exit(benchmark.main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] in ("render", "schema", "formats"):
        from talkgenerator.plan import external

        sys.exit(external.main(sys.argv[1], sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] in ("login", "logout"):
        from talkgenerator.llm import login

        sys.exit(login.main(sys.argv[1], sys.argv[2:]))
    args = generator.get_argument_parser().parse_args()
    main(args)


def _mcp(argv):
    mcp_server = _mcp_server()
    if mcp_server is None:
        print(MCP_MISSING, file=sys.stderr)
        return 2
    return mcp_server.main(argv)


def _mcp_server():
    """The MCP server's module, or None when the optional MCP SDK isn't installed."""
    try:
        from talkgenerator import mcp_server
    except ModuleNotFoundError as error:
        if (error.name or "").partition(".")[0] != "mcp":
            raise
        return None
    return mcp_server


if __name__ == "__main__":
    main_cli()
