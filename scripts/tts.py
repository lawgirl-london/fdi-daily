"""Turn out/episode.json's script into out/episode.mp3 with Edge TTS."""
import asyncio
import json
import re
import sys
import time

import edge_tts

CONFIG = json.load(open("config.json"))


def prepare(text: str) -> str:
    # Longest keys first so e.g. "NSI Act" wins over "NSI".
    for word in sorted(CONFIG["pronunciations"], key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(word)}\b", CONFIG["pronunciations"][word], text)
    return text


async def synthesise(text: str, path: str) -> None:
    await edge_tts.Communicate(text, CONFIG["voice"], rate=CONFIG["rate"]).save(path)


def main() -> None:
    episode = json.load(open("out/episode.json"))
    script = episode["script"].strip()
    words = len(script.split())
    print(f"Script: {words} words (cap {CONFIG['max_words']})")
    if words > CONFIG["max_words"] * 1.15:
        sys.exit(f"Script too long: {words} words")

    text = prepare(script)
    for attempt in range(1, 4):
        try:
            asyncio.run(synthesise(text, "out/episode.mp3"))
            return
        except Exception as e:  # network hiccups from the TTS endpoint
            print(f"TTS attempt {attempt} failed: {e}")
            time.sleep(10 * attempt)
    sys.exit("TTS failed after 3 attempts")


if __name__ == "__main__":
    main()
