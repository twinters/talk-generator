import time

from talkgenerator import generator
from talkgenerator.util import os_util


def run_time_test(start_idx, end_idx):
    words = os_util.read_lines("data/eval/common_words.txt")[start_idx:end_idx]
    result_file = open("data/eval/timings.txt", "a+")

    for topic in words:
        args = generator.get_argument_parser().parse_args(
            [
                "--topic",
                topic,
                "--num_slides",
                "7",
                "--save_ppt",
                "True",
                "--open_ppt",
                "False",
                "--parallel",
                "True",
            ]
        )

        start = time.process_time()
        clock_start = time.perf_counter()

        generator.generate_presentation_using_cli_arguments(args)

        end = time.process_time()
        clock_end = time.perf_counter()
        timing = end - start
        clock_timing = clock_end - clock_start
        print(
            ("It took {} seconds to generate the presentation" + ", and {} seconds system-wide").format(
                str(timing), str(clock_timing)
            )
        )
        result_file.write(topic + ", " + str(timing) + ", " + str(clock_timing) + "\n")
        result_file.flush()

    result_file.close()


# run_time_test(0, 200)
