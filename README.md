# 10-millions-tokens

A long-context reading challenge: follow a hidden, shuffled trail through 100
large story files and report the order in which you visited them.

The current size specification is **100 numbered files of exactly 100,000 words
each**, plus a short start file. That is **10 million words**, not exactly 10
million tokens. The checked-in challenge measures **13,729,178 tokens** using
`tiktoken` 0.12.0 with `cl100k_base`, including the start file. The repository name
is a scale label; token totals depend on the tokenizer.

## Solve the challenge

Begin with [task/start_instruction.md](task/start_instruction.md). Read that file
fully, then follow its direction to the next file. Read each requested file from
beginning to end before following its embedded direction. Numbered files live
in `task/` and are named `instruction_1.md` through `instruction_100.md`.

Each numbered file contains story text and exactly one challenge direction at a
random paragraph boundary. Directions use different wording and may identify a
file by its filename, decimal number, English number, or Roman numeral. Convert
described numbers to decimal filenames: for example, “numbered twelve” means
`instruction_12.md`. The final file contains an explicit stop instruction.

At the end, write `solution.txt` containing `start_instruction.md` followed by all
100 numbered filenames in the order visited, one filename per line. Include no
directory paths, commentary, or Markdown fences. Every numbered file appears
exactly once. An illustrative prefix, **not the answer**, is:

```text
start_instruction.md
instruction_45.md
instruction_17.md
...
```

For an evaluation, require full sequential reading and prohibit search, regex,
scripts, the maintainer tools, and the reference answer. Varied wording does not
prevent automated extraction, and the repository alone cannot force an agent to
consume a particular number of tokens. Actual usage also depends on caching,
truncation, rereading, and the model's tokenizer. Give a solver only `task/` and
the accompanying source license; keep maintenance artifacts outside its inputs.

## Corpus and measurements

| Property | Checked-in value |
| --- | ---: |
| Numbered story files | 100 |
| Words per numbered file | 100,000 |
| Start-file words | 121 |
| Total words, including start | 10,000,121 |
| Total `cl100k_base` tokens | 13,729,178 |
| Tokens per numbered file | 133,713–140,129 |
| Distinct next-file sentences | 100 |
| Stop sentences | 1 |

Words are counted with Python's `str.split()` (whitespace-delimited words),
including each file's attribution and direction. [manifest.json](manifest.json)
records measured word/token counts and SHA-256 hashes for every file, in numeric
filename order; it does not record the solution order or a random seed.

The filler is *War and Peace* by Leo Tolstoy, translated by Louise and Aylmer
Maude, from [Project Gutenberg ebook 2600](https://www.gutenberg.org/ebooks/2600).
Project Gutenberg lists this edition as public domain in the USA. Credits:
An Anonymous Volunteer and David Widger. The downloaded text contains 563,286
words between its ebook markers, including its table of contents. To reach the
requested size, the generator cycles through that text, using 17 complete passes
and part of an eighteenth, and splits the stream into 100 chunks at word
boundaries. Original prose and paragraph spacing are preserved inside chunks;
challenge directions are inserted between paragraphs.

Source: [UTF-8 text](https://www.gutenberg.org/cache/epub/2600/pg2600.txt).
The pinned download SHA-256 is:

```text
2d5bb2ad5f422765e714617e21fa31bbaf8958aa79682c86fca6660fcc5d1b2b
```

The source header and full Project Gutenberg terms are retained in
[sources/gutenberg-license.txt](sources/gutenberg-license.txt). Each story file
identifies the modifications and links to those terms. The repository's
[Apache 2.0 license](LICENSE) applies to its original code and challenge material;
the book retains its own public-domain status and accompanying distribution
terms. The original unmodified download is not committed.

## Reference solution

[solution/solution.zip](solution/solution.zip) contains two files, both compressed
and encrypted with AES-256 ZIP encryption:

- `solution.txt`: the complete ordered list of filenames.
- `secret_sentences.json`: a mapping from each of the 101 filenames to its exact
  embedded challenge `sentence` and expected `next_file`. The final stop file has
  `next_file: null`. The start file is included, and keys are in numeric filename
  order after the start file, independently of the solution order.

For example, one illustrative entry (not an actual answer) has this shape:

```json
{
  "instruction_45.md": {
    "sentence": "After reading this file completely, continue to instruction_17.md.",
    "next_file": "instruction_17.md"
  }
}
```

This supports a later script or AI audit: confirm that each exact sentence occurs
once in its named file, then judge whether its wording clearly and fairly directs
the reader to `next_file` (or clearly ends the trail for `null`). The verifier
already checks exact embedding and agreement with the reference traversal;
semantic fairness can be reviewed separately using this mapping.

Both answer artifacts are constructed in memory and written directly into the
encrypted archive: neither plaintext artifact is written to disk or committed.

Generation creates a random 256-bit password in `.solution-password`, with
owner-only filesystem permissions. That file is Git-ignored and **is not
included in a clone**. The maintainer must retain it separately and share it only
when revealing the answer. The README intentionally does not contain it.

Use an AES-compatible ZIP tool such as 7-Zip to extract the solution, entering
the password when prompted:

```sh
7z x solution/solution.zip -osolution
```

Both extracted answer files are also Git-ignored. Python's standard
`zipfile` module and some system `unzip` versions do not support this encryption;
the verifier below uses `pyzipper` and reads the answer in memory.

## Maintainer commands

Use Python 3.10 or newer with virtual environment support:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/build_task.py verify
.venv/bin/python -m unittest discover -s tests -v
```

Verification needs `.solution-password`, or a separately supplied password file:

```sh
.venv/bin/python scripts/build_task.py verify --password-file /path/to/password-file
```

It checks all 101 files, their word and token counts and hashes, exactly one
direction per file, 100 distinct transition wordings, a complete traversal with
no cycles, an explicit terminal stop, and agreement with both encrypted answer
artifacts. It checks each secret sentence occurs exactly once, matches its file,
and names the expected successor. It also checks AES-256 encryption of both ZIP
members and rejects missing or incorrect passwords. The tests exercise missing
and modified files, a cycle, an incorrect encrypted answer or secret sentence,
password failures, and refusal to overwrite existing artifacts.

To build a fresh challenge, choose a new output directory:

```sh
.venv/bin/python scripts/build_task.py generate --output /tmp/new-reading-trail
```

The generator downloads the source over HTTPS and verifies its pinned checksum.
For an already downloaded copy, add `--source /path/to/pg2600.txt`; the checksum
is still verified. Initial tokenization may also download the `cl100k_base`
encoding data. `--words` changes the word target for a new generation (default:
100,000). Generation refuses to overwrite existing challenge artifacts.

Each run chooses a fresh random permutation of 1–100, separately shuffles 100
different sentence templates, and randomly places one direction into each story
chunk. The start file points to the first shuffled number; 99 numbered files
point to their successors, and the remaining file ends the trail. It saves the
encrypted answer and secret sentences, private password, source terms, and
manifest, then validates the result. No seed or plaintext answer artifact is saved.
Regenerated challenges have
different answers and measured token totals; update the table above if replacing
the checked-in corpus.
