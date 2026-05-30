import sys
from khatt.pipeline import run

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Khatt Engine — Linguistically correct Arabic calligraphy"
    )
    parser.add_argument("text",    help="Arabic text to render")
    parser.add_argument("--style", default="thuluth",
                        choices=["thuluth", "naskh", "diwani",
                                 "nastaliq", "ruqah", "kufic"],
                        help="Calligraphy style (default: thuluth)")
    args = parser.parse_args()
    run(args.text, args.style)

if __name__ == "__main__":
    main()