# Use it with Claude

Claude can write the talk itself, on your own Claude plan, and leave the rest to talkgenerator: finding images it may
use, crediting them on the slides, laying out the deck and saving the PowerPoint. Claude writes a plan (what every
slide says, and what its images should show), talkgenerator turns it into a deck and reports back, and Claude fixes
the slides that didn't come out.

There are two ways to set this up, and they work together:

| | The Skill | The MCP server |
| --- | --- | --- |
| What it is | Instructions that teach Claude what makes a good karaoke talk, and how to use talkgenerator's commands | `talkgenerator mcp`: talkgenerator's commands as tools, on your computer |
| Where it works | [Claude Code](https://claude.com/claude-code), and wherever else Claude can run commands; in claude.ai, Claude writes the plan and you render it | [Claude Desktop](https://claude.ai/download), Claude Code and other MCP clients |
| What to install | `pip install talkgenerator` | `pip install 'talkgenerator[mcp]'` |

In Claude Code, the Skill is all you need: Claude runs the commands itself. In Claude Desktop, add the MCP server, so
that Claude can make the decks, and the Skill as well if you like, as it knows more about what makes a good talk.
Nothing goes through talkgenerator.com: talkgenerator works with your own [keys](configuration.md) and
[language model settings](language-models.md).

## Plans and decks

A plan is the talk as Claude writes it: its title, the presenter's job and made-up name, its thesis, and every
slide's kind, texts and image search queries, as JSON (`talkgenerator schema plan` prints its JSON Schema). It holds
words and queries, never image addresses, so finding, licensing and crediting images stays talkgenerator's job.

`talkgenerator render` turns a plan into a deck, the talk as data with every image found and credited, and draws the
PowerPoint from that deck. It saves the deck's JSON (`<name>.deck.json`) next to the PowerPoint: the deck is what the
PowerPoint is drawn from, so a saved deck renders as the same PowerPoint again (see [Python](python.md#decks)).

## The Skill

1. Install talkgenerator where Claude runs its commands, `pip install talkgenerator`, and put the API keys you have
   in a `.env` file (see [Keys and settings](configuration.md)).
2. Add the Skill to Claude:
   - In **Claude Code**, install it as a plugin, straight from this repository:

     ```
     /plugin marketplace add twinters/talk-generator
     /plugin install talkgenerator@talk-generator
     ```

     Or copy the [`skill/skills/talkgenerator`](https://github.com/twinters/talk-generator/tree/master/skill/skills/talkgenerator)
     folder into `~/.claude/skills/`, for all your projects, or into a project's `.claude/skills/`.
   - In **claude.ai** and the Claude apps, zip that `talkgenerator` folder (so that the zip holds
     `talkgenerator/SKILL.md`), and upload it under Customize > Skills: "+", then "Create skill", then "Upload a
     skill". Skills need code execution, which you turn on under Settings > Capabilities. Claude's sandbox there may
     not be able to install talkgenerator or reach the image sources. Claude then gives you the plan as a JSON file,
     which you render on your computer with `talkgenerator render plan.json`, or which Claude Desktop renders itself
     with the [MCP server](#the-mcp-server).
3. Ask Claude for, say, "a 10-slide PowerPoint karaoke deck about competitive birdwatching".

The commands the Skill uses work for plans written by hand, or by other tools, too:

| Command | What it does |
| --- | --- |
| `talkgenerator render plan.json [-o talk.pptx]` | Turns a plan (or several: `plans/*.json`) into a PowerPoint, with the deck's JSON and a contact sheet of its images next to it, and prints a report in JSON: per slide, whether it came out as planned, was made the classic way instead, or was left out, and why, and what every image was searched with |
| `talkgenerator formats [--details] [--json]` | The talk formats, and with `--details` the slides a plan can have: their texts, length limits, images and recipes |
| `talkgenerator schema plan` | The plan format, as a JSON Schema (`schema deck` for the deck format) |

[An example plan](https://github.com/twinters/talk-generator/blob/master/skill/skills/talkgenerator/references/example-plan.json)
shows what goes in one, and [the command line](command-line.md#rendering-a-plan-talkgenerator-render) lists
`render`'s options.

## The MCP server

`talkgenerator mcp` is a local [MCP](https://modelcontextprotocol.io/) server: it gives talkgenerator's commands as
tools to Claude Desktop and other MCP clients, so Claude can make decks in a chat, without a shell. The client starts
it on your own computer, where it uses your own keys and saves the decks in a folder of yours. Nothing of it is
hosted.

| Tool | What it does |
| --- | --- |
| `list_formats` | The talk formats, themes, languages and name styles |
| `describe_format` | The slides a plan for a format can have (as `talkgenerator formats --details --json`) |
| `get_plan_schema` | The plan format, as a JSON Schema (as `talkgenerator schema plan`) |
| `render_plan` | Turns a plan into a PowerPoint, and returns the report of `talkgenerator render`, with the paths of the files it saved |
| `generate_talk` | Makes a whole talk on a topic, as `talkgenerator --topic` does (or with a title, or on a `topic_or_title`): the language model of your settings writes it (OpenRouter's free models, when you have an OpenRouter key), at the level of your settings (`TALKGENERATOR_LLM_LEVEL`, or the server's `--llm_level`; without either, `advanced` on a model that costs, which plans the talk first, for cleverer talks), or else the classic generator. Returns where the files are, the talk's seed, its level, and the checks |

1. Install talkgenerator with the MCP SDK on your computer: `pip install 'talkgenerator[mcp]'`. On Windows on Arm,
   install it in an x64 Python: the MCP SDK needs the `cryptography` package, which has no wheels for Windows on Arm.
2. Add the server to your MCP client:
   - In **Claude Desktop**, Settings > Developer > Edit Config opens its config file, `claude_desktop_config.json`.
     Add the server under `mcpServers`, next to what the file holds already, with the API keys you have under `env`:

     ```json
     {
       "mcpServers": {
         "talkgenerator": {
           "command": "talkgenerator",
           "args": ["mcp"],
           "env": {
             "UNSPLASH_ACCESS_KEY": "...",
             "PEXELS_KEY": "..."
           }
         }
       }
     }
     ```

     Then quit Claude Desktop completely (closing its window leaves it running) and start it again: talkgenerator
     shows up among the connectors, under the "+" button of a chat.
   - In **Claude Code**, for all your projects (keys go in `--env NAME=value` options, before `--transport`):

     ```sh
     claude mcp add --transport stdio --scope user talkgenerator -- talkgenerator mcp
     ```

   - In **other MCP clients**: the command `talkgenerator`, with the argument `mcp`, over stdio.
3. Ask Claude for, say, "a PowerPoint karaoke deck about competitive birdwatching". The server tells Claude how to
   write a plan, and when to render it again.

Good to know:

- If the client doesn't find the `talkgenerator` command, give its full path, such as
  `"/Users/you/talks/.venv/bin/talkgenerator"`, or on Windows `"C:\\Users\\you\\talks\\.venv\\Scripts\\talkgenerator.exe"`
  (JSON doubles the backslashes). With [uv](https://docs.astral.sh/uv/), there's nothing to install first: use
  `"command": "uvx"`, with `"args": ["--from", "talkgenerator[mcp]", "talkgenerator", "mcp"]` (on Windows on Arm, put
  `"--python", "cpython-3.13-windows-x86_64-none"` in front of those).
- Claude Desktop starts the server in a folder of its own, where your `.env` isn't: that's why the keys go under
  `env`. A key that `talkgenerator login openrouter` got needs no entry, and neither does a sign-in with
  `talkgenerator login chatgpt`: the server finds them in your config folder. It also finds the `.env` of a clone of
  this repository when it runs from that clone (installed with `pip install -e '.[mcp]'`).
- Every other setting works under `env` too, such as `TALKGENERATOR_LLM` (see [Language models](language-models.md)),
  which is the only way to have a paid model write the talks: a tool call can't pick one. For Gemini, say, that's
  `"TALKGENERATOR_LLM": "gemini"` and `"GEMINI_API_KEY": "..."`, with talkgenerator installed as
  `talkgenerator[mcp,gemini]`.
- The decks go to a `talkgenerator` folder in your documents, or to the folder that
  `"args": ["mcp", "--output_folder", "<folder>"]` names, and nowhere else. They never overwrite a file: a deck made
  again gets a name of its own.
- If the server doesn't show up, run `talkgenerator mcp` in a terminal: it should say that it serves its tools, and
  wait (Ctrl+C stops it). Claude Desktop keeps what the server logs in `mcp-server-talkgenerator.log`, in its logs
  folder: on Windows, the `logs` folder next to the config file; on macOS, `~/Library/Logs/Claude`.
