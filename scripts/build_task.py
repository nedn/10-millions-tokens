#!/usr/bin/env python3
"""Build and validate a randomized, word-counted reading trail."""

import argparse
import hashlib
import itertools
import json
import re
import random
import secrets
from pathlib import Path
from urllib.request import urlopen

try:
    from .number_fuzzer import representations
except ImportError:  # Direct script execution.
    from number_fuzzer import representations

ROOT = Path(__file__).resolve().parents[1]
COUNT = 100
DECOYS_PER_FILE = 100
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
Labels may use words, numeral bases, arithmetic, equations, or counting clues.
Evaluate each label as an integer N and open the corresponding numbered sibling.
References to volumes, entries, bindings, and catalog positions mean these files.
Record this filename first, then every numbered filename in the order visited.
Follow only the embedded challenge directions, not dialogue in the story.
Ignore lookalike directions whose labels do not specify an integer destination.
At the explicit stop instruction, write the recorded filenames to solution.txt,
one filename per line, without paths, numbering, or commentary.

"""
STOP = (
    "This is the last file in the trail; stop reading and write solution.txt with "
    "start_instruction.md followed by the numbered filenames in the order you visited them."
)
TEMPLATES = (ROOT / "scripts/directions.txt").read_text(encoding="utf-8").splitlines()

# None of these labels denotes a number or an existing file. Their combinations
# are deliberately ordinary words, without a dedicated decoy marker.
DECOY_LABELS = tuple(
    f"the {adjective} {noun}"
    for adjective in (
        "faded", "folded", "dusty", "velvet", "forgotten", "torn", "silver",
        "scarlet", "sealed", "missing", "weathered", "embroidered", "wooden",
        "painted", "crumpled", "unmarked", "violet", "frayed", "polished", "silent")
    for noun in (
        "ribbon", "envelope", "seal", "portrait", "curtain", "lantern", "bookmark",
        "letter", "satchel", "medallion", "banner", "mirror", "cabinet", "chest",
        "compass", "key", "map", "journal", "tapestry", "window"))


def generate_decoys(rng):
    """Use each real direction template once, with a nonnumeric label."""
    templates = list(TEMPLATES)
    rng.shuffle(templates)
    labels = rng.sample(DECOY_LABELS, DECOYS_PER_FILE)
    return [template.format(target=label) for template, label in zip(templates, labels)]


def intersperse(prose, sentences, rng):
    """Random interior paragraph positions; no special position for the real clue."""
    if len(prose) < 2:
        raise ValueError("Need at least two prose paragraphs for inserting directions.")
    sentences = list(sentences)
    rng.shuffle(sentences)
    boundaries = range(1, len(prose))
    positions = (rng.sample(boundaries, len(sentences)) if len(boundaries) >= len(sentences)
                 else [rng.choice(boundaries) for _ in sentences])
    inserts = {}
    for position, sentence in zip(positions, sentences):
        inserts.setdefault(position, []).append(sentence)
    result = []
    for position, paragraph in enumerate(prose):
        result.extend(inserts.get(position, []))
        result.append(paragraph)
    return result


def template_parser():
    branches = []
    for template, wording in enumerate(TEMPLATES):
        if wording.count("{target}") != 1:
            raise ValueError("Each template needs exactly one target.")
        prefix, suffix = wording.split("{target}")
        branches.append(re.escape(prefix) + f"(?P<t{template}>.+)" + re.escape(suffix))
    pattern = re.compile("(?:" + "|".join(branches) + ")")

    def parse(sentence):
        match = pattern.fullmatch(sentence)
        return (int(match.lastgroup[1:]), match[match.lastgroup]) if match else None
    return parse


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


def direction(template, number, style=0):
    return TEMPLATES[template].format(
        target=representations(number, english, roman)[style])


def direction_parser():
    """Decode independent template/number choices without knowing the trail."""
    if len(TEMPLATES) != COUNT or len(set(TEMPLATES)) != COUNT:
        raise ValueError("Expected 100 unique sentence templates.")
    expressions = {}
    for number in range(1, COUNT + 1):
        forms = representations(number, english, roman)
        if len(forms) != COUNT or len(set(forms)) != COUNT:
            raise ValueError("Expected 100 distinct number encodings.")
        for style, expression in enumerate(forms):
            if expression in expressions:
                raise ValueError("Ambiguous number encoding.")
            expressions[expression] = (filename(number), style)
    parse_template = template_parser()

    def parse(sentence):
        match = parse_template(sentence)
        if match and match[1] in expressions:
            destination, style = expressions[match[1]]
            return destination, match[0], style
        return None
    return parse


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
    import pyzipper

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


def generate_directions(rng):
    """Share the exact shuffle/composition path between builds and previews."""
    order = list(range(1, COUNT + 1))
    templates = list(range(COUNT))
    rng.shuffle(order)
    rng.shuffle(templates)
    styles = list(range(COUNT))
    rng.shuffle(styles)
    return [(number, direction(template, number, style))
            for number, template, style in zip(order, templates, styles)]


def build(root, source, words=WORDS):
    """Generate fresh artifacts; never overwrite an existing challenge."""
    import tiktoken

    if words < 5000:
        raise ValueError("Use at least 5000 words per numbered file to fit 100 decoys and prose.")
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
    transitions = generate_directions(rng)
    names = ["start_instruction.md"] + [filename(number) for number, _ in transitions]
    directions = {names[i]: sentence for i, (_, sentence) in enumerate(transitions)}
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
            insertions = [sentence] + generate_decoys(rng)
            budget = words - len(HEADER.split()) - sum(len(s.split()) for s in insertions)
            chunk = list(itertools.islice(stream, budget))
            prose_words += budget
            prose = re.split(r"\n\s*\n", "".join(chunk).strip())
            content = HEADER + "\n\n".join(intersperse(prose, insertions, rng)) + "\n"
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
        "decoys_per_numbered_file": DECOYS_PER_FILE,
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
    import pyzipper
    import tiktoken

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    expected = {"start_instruction.md"} | {filename(n) for n in range(1, COUNT + 1)}
    actual = {p.name for p in (root / "task").iterdir()}
    if actual != expected or set(manifest["files"]) != expected:
        raise ValueError("Expected exactly one start file and 100 numbered files.")
    parse_direction = direction_parser()
    parse_template = template_parser()
    decoy_labels = set(DECOY_LABELS)
    decoy_count = manifest.get("decoys_per_numbered_file", 0)
    if decoy_count not in (0, DECOYS_PER_FILE):
        raise ValueError("Unsupported decoy count.")
    encoder = tiktoken.get_encoding(manifest["token_encoding"])
    edges, templates, styles, evidence = {}, [], [], {}
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
        decoys = [match[0] for p in paragraphs
                  if (match := parse_template(p.strip())) and match[1] in decoy_labels]
        expected_decoys = decoy_count if name != "start_instruction.md" else 0
        if len(decoys) != expected_decoys or (expected_decoys and sorted(decoys) != list(range(COUNT))):
            raise ValueError(f"Wrong decoy count or template coverage: {name}")
        parsed = [(p.strip(), parse_direction(p.strip())) for p in paragraphs]
        sentences = [sentence for sentence, match in parsed if match]
        found = [match for _, match in parsed if match]
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
            styles.append(found[0][2])
        total_words += words
        total_tokens += tokens
    if sorted(templates) != list(range(COUNT)):
        raise ValueError("Expected 100 distinct transition wordings.")
    if sorted(styles) != list(range(COUNT)):
        raise ValueError("Expected 100 distinct destination encodings.")
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
    parser.add_argument("command", choices=("generate", "verify"), nargs="?")
    parser.add_argument("--debug-instruction-gen", type=int, metavar="SEED",
                        help="Print 100 reproducible directions using SEED, without creating files.")
    parser.add_argument("--output", type=Path, default=ROOT)
    parser.add_argument("--source", type=Path, help="Use a previously downloaded source (checksum checked).")
    parser.add_argument("--words", type=int, default=WORDS)
    parser.add_argument("--password-file", type=Path, help="Verification only; defaults to OUTPUT/.solution-password.")
    args = parser.parse_args()
    if args.debug_instruction_gen is not None:
        if args.command is not None:
            parser.error("--debug-instruction-gen is standalone; omit generate or verify.")
        for _, sentence in generate_directions(random.Random(args.debug_instruction_gen)):
            print(sentence)
        return
    if args.command is None:
        parser.error("choose generate, verify, or --debug-instruction-gen SEED")
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
