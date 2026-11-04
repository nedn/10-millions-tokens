#!/usr/bin/env python3
"""Build and validate a randomized, word-counted reading trail."""

import argparse
import hashlib
import itertools
import json
import re
import secrets
from pathlib import Path
from urllib.request import urlopen

import pyzipper
import tiktoken

ROOT = Path(__file__).resolve().parents[1]
COUNT = 100
WORDS = 100_000
SOURCE_URL = "https://www.gutenberg.org/cache/epub/2600/pg2600.txt"
SOURCE_SHA256 = "2d5bb2ad5f422765e714617e21fa31bbaf8958aa79682c86fca6660fcc5d1b2b"
START_MARKER = "*** START OF THE PROJECT GUTENBERG EBOOK WAR AND PEACE ***"
END_MARKER = "*** END OF THE PROJECT GUTENBERG EBOOK WAR AND PEACE ***"
HEADER = """# Reading trail

Modified excerpts from *War and Peace* by Leo Tolstoy, translated by
Louise and Aylmer Maude; repeated, split, and interspersed with challenge directions.

This eBook is for the use of anyone anywhere in the United States and most
other parts of the world at no cost and with almost no restrictions whatsoever.
You may copy it, give it away or re-use it under the terms of the
[Project Gutenberg License](../sources/gutenberg-license.txt) included with this eBook
or online at [www.gutenberg.org](https://www.gutenberg.org).

"""
START = """# Start the reading trail

Read each requested document fully, from top to bottom, before following its
embedded direction. All numbered files are siblings of this file, named
instruction_N.md, with N written in ordinary decimal digits from 1 through 100.
Directions may describe N using digits, English words, or Roman numerals.
Record this filename first, then every numbered filename in the order visited.
Follow only the embedded challenge directions, not dialogue in the story.
At the explicit stop instruction, write the recorded filenames to solution.txt,
one filename per line, without paths, numbering, or commentary.

"""
STOP = (
    "This is the last file in the trail; stop reading and write solution.txt with "
    "start_instruction.md followed by the numbered filenames in the order you visited them."
)
TEMPLATES = (ROOT / "scripts/directions.txt").read_text(encoding="utf-8").splitlines()


def filename(number):
    return f"instruction_{number}.md"


def english(number):
    small = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
    tens = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()
    if number == 100:
        return "one hundred"
    if number < 20:
        return small[number]
    return tens[number // 10] + ("-" + small[number % 10] if number % 10 else "")


def roman(number):
    result = ""
    for value, letters in ((100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
                           (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while number >= value:
            result += letters
            number -= value
    return result


def direction(template, number):
    targets = (
        f"`{filename(number)}`",
        f"the instruction file numbered {english(number)}",
        f"the Markdown instruction file whose numeric suffix is {number}",
        f"the instruction file whose number is {roman(number)} in Roman numerals",
    )
    return TEMPLATES[template].format(target=targets[template % 4])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_private(path, text):
    # Exclusive creation and restrictive permissions from the first write.
    import os
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def write_solution(root, names, directions, password):
    """Write both answer artifacts directly to an encrypted archive, atomically."""
    successors = dict(zip(names, names[1:] + [None]))
    evidence = {name: {"sentence": directions[name], "next_file": successors[name]}
                for name in ["start_instruction.md"] + [filename(n) for n in range(1, COUNT + 1)]}
    temporary = root / "solution/solution.zip.tmp"
    with pyzipper.AESZipFile(temporary, "w", compression=pyzipper.ZIP_DEFLATED,
                            encryption=pyzipper.WZ_AES) as archive:
        archive.setpassword(password.encode())
        archive.setencryption(pyzipper.WZ_AES, nbits=256)
        archive.writestr("solution.txt", "\n".join(names) + "\n")
        archive.writestr("secret_sentences.json", json.dumps(evidence, indent=2) + "\n")
    temporary.replace(root / "solution/solution.zip")


def build(root, source, words=WORDS):
    """Generate fresh artifacts; never overwrite an existing challenge."""
    if words < 250:
        raise ValueError("Use at least 250 words per numbered file.")
    outputs = ("task", "solution", "manifest.json", ".solution-password", "sources")
    if any((root / name).exists() for name in outputs):
        raise ValueError("Output already contains challenge artifacts; choose a new --output directory.")
    text = source.decode("utf-8-sig").replace("\r\n", "\n")
    front, remainder = text.split(START_MARKER, 1)
    body, back = remainder.split(END_MARKER, 1)
    # Preserve prose and whitespace. Only chunk boundaries can split paragraphs.
    source_words = re.findall(r"\S+\s*", body.strip())
    if not source_words:
        raise ValueError("The source contains no story text.")
    source_words[-1] = source_words[-1].rstrip() + "\n\n"
    stream = itertools.cycle(source_words)
    rng = secrets.SystemRandom()
    order = list(range(1, COUNT + 1))
    templates = list(range(COUNT))
    rng.shuffle(order)
    rng.shuffle(templates)
    names = ["start_instruction.md"] + [filename(n) for n in order]
    directions = {names[i]: direction(templates[i], order[i]) for i in range(COUNT)}
    directions[names[-1]] = STOP
    root.mkdir(parents=True, exist_ok=True)
    for name in ("task", "solution", "sources"):
        (root / name).mkdir()
    license_text = "\n".join(line.rstrip() for line in (front + back).splitlines()).rstrip() + "\n"
    (root / "sources/gutenberg-license.txt").write_text(license_text, encoding="utf-8")
    encoder = tiktoken.get_encoding("cl100k_base")
    records = {}
    prose_words = 0
    for name in ["start_instruction.md"] + [filename(n) for n in range(1, COUNT + 1)]:
        sentence = directions[name]
        if name == "start_instruction.md":
            content = START + sentence + "\n"
        else:
            budget = words - len(HEADER.split()) - len(sentence.split())
            chunk = list(itertools.islice(stream, budget))
            prose_words += budget
            # Choose an interior paragraph boundary; directions remain unmarked prose.
            boundaries = [i + 1 for i, word in enumerate(chunk[:-1]) if "\n\n" in word]
            if not boundaries:
                raise ValueError("No paragraph boundary available for inserting a direction.")
            position = rng.choice(boundaries)
            content = (HEADER + "".join(chunk[:position]).rstrip() + "\n\n" + sentence +
                       "\n\n" + "".join(chunk[position:]).strip() + "\n")
            if len(content.split()) != words:
                raise ValueError(f"Unexpected word count in {name}.")
        data = content.encode("utf-8")
        (root / "task" / name).write_bytes(data)
        records[name] = {"words": len(content.split()),
                         "tokens": len(encoder.encode_ordinary(content)),
                         "sha256": digest(data)}
    # No plaintext solution or random seed is ever written to disk.
    password = secrets.token_urlsafe(32)
    write_private(root / ".solution-password", password + "\n")
    write_solution(root, names, directions, password)
    manifest = {
        "numbered_files": COUNT, "words_per_numbered_file": words,
        "word_count_method": "Python str.split (whitespace-delimited words)",
        "token_encoding": "cl100k_base", "tiktoken_version": tiktoken.__version__,
        "source_url": SOURCE_URL, "source_sha256": digest(source),
        "source_words": len(source_words), "prose_words_used": prose_words,
        "source_passes": (prose_words + len(source_words) - 1) // len(source_words),
        "total_words": sum(item["words"] for item in records.values()),
        "total_tokens": sum(item["tokens"] for item in records.values()),
        "files": records,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify(root, password_file):
    """Check corpus, independently reconstruct the graph, and compare encrypted answer."""
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    expected = {"start_instruction.md"} | {filename(n) for n in range(1, COUNT + 1)}
    actual = {p.name for p in (root / "task").iterdir()}
    if actual != expected or set(manifest["files"]) != expected:
        raise ValueError("Expected exactly one start file and 100 numbered files.")
    candidates = {direction(t, n): (filename(n), t)
                  for t in range(COUNT) for n in range(1, COUNT + 1)}
    encoder = tiktoken.get_encoding(manifest["token_encoding"])
    edges, templates, evidence = {}, [], {}
    total_words = total_tokens = 0
    for name in sorted(expected):
        data = (root / "task" / name).read_bytes()
        content = data.decode("utf-8")
        words, tokens = len(content.split()), len(encoder.encode_ordinary(content))
        if manifest["files"][name] != {"words": words, "tokens": tokens, "sha256": digest(data)}:
            raise ValueError(f"Content or count mismatch: {name}")
        if name != "start_instruction.md" and words != manifest["words_per_numbered_file"]:
            raise ValueError(f"Wrong word count: {name}")
        paragraphs = content.split("\n\n")
        sentences = [p.strip() for p in paragraphs if p.strip() in candidates]
        found = [candidates[sentence] for sentence in sentences]
        stops = sum(p.strip() == STOP for p in paragraphs)
        if len(found) + stops != 1:
            raise ValueError(f"Expected one direction or stop: {name}")
        edges[name] = found[0][0] if found else None
        sentence = sentences[0] if found else STOP
        if content.count(sentence) != 1:
            raise ValueError(f"The secret sentence must appear exactly once: {name}")
        evidence[name] = {"sentence": sentence, "next_file": edges[name]}
        if found:
            templates.append(found[0][1])
        total_words += words
        total_tokens += tokens
    if sorted(templates) != list(range(COUNT)):
        raise ValueError("Expected 100 distinct transition wordings.")
    if total_words != manifest["total_words"] or total_tokens != manifest["total_tokens"]:
        raise ValueError("Manifest totals do not match the corpus.")
    visited, current = [], "start_instruction.md"
    while current is not None:
        if current in visited or current not in edges:
            raise ValueError("The trail contains a cycle or an invalid destination.")
        visited.append(current)
        current = edges[current]
    if set(visited) != expected:
        raise ValueError("The trail stops before visiting every file.")
    password = password_file.read_text(encoding="utf-8").strip().encode()
    with pyzipper.AESZipFile(root / "solution/solution.zip") as archive:
        if sorted(archive.namelist()) != ["secret_sentences.json", "solution.txt"]:
            raise ValueError("The archive must contain only solution.txt and secret_sentences.json.")
        for member in archive.namelist():
            info = archive.getinfo(member)
            if not info.flag_bits & 1 or info.wz_aes_strength != 3:
                raise ValueError("Both solution artifacts must use AES-256 ZIP encryption.")
            for bad_password in (None, b"deliberately-wrong-password"):
                try:
                    archive.read(member, pwd=bad_password)
                except RuntimeError:
                    pass
                else:
                    raise ValueError("A solution artifact was readable without the correct password.")
        answer = archive.read("solution.txt", pwd=password).decode("utf-8")
        if answer != "\n".join(visited) + "\n":
            raise ValueError("The encrypted solution does not match the reading trail.")
        secret_sentences = json.loads(archive.read("secret_sentences.json", pwd=password))
        if secret_sentences != evidence:
            raise ValueError("The encrypted secret sentences do not match the embedded directions.")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "verify"))
    parser.add_argument("--output", type=Path, default=ROOT)
    parser.add_argument("--source", type=Path, help="Use a previously downloaded source (checksum checked).")
    parser.add_argument("--words", type=int, default=WORDS)
    parser.add_argument("--password-file", type=Path, help="Verification only; defaults to OUTPUT/.solution-password.")
    args = parser.parse_args()
    if args.command == "generate":
        if args.source:
            source = args.source.read_bytes()
        else:
            with urlopen(SOURCE_URL, timeout=60) as response:
                source = response.read()
        if digest(source) != SOURCE_SHA256:
            raise ValueError("Source checksum changed; review the new source before updating the pinned checksum.")
        build(args.output, source, args.words)
    result = verify(args.output, args.password_file or args.output / ".solution-password")
    print(f"Validated 101 files, {result['total_words']:,} words, "
          f"{result['total_tokens']:,} cl100k_base tokens, and the AES-256 solution ZIP.")
    if args.command == "generate":
        print(f"Random password saved privately to {args.output / '.solution-password'}")


if __name__ == "__main__":
    main()
