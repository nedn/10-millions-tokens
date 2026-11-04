# 10-millions-tokens

A long-context reading challenge: follow a hidden, shuffled trail through 100
large story files and report the order in which you visited them.

The current size specification is **100 numbered files of exactly 100,000 words
each**, plus a short start file. That is **10 million words**, not exactly 10
million tokens. The checked-in challenge measures **12,855,072 tokens** using
`tiktoken` 0.12.0 with `cl100k_base`, including the start file. The repository name
is a scale label; token totals depend on the tokenizer.

## Solve the challenge

Begin with [task/start_instruction.md](task/start_instruction.md). Read that file
fully, then follow its direction to the next file. Read each requested file from
beginning to end before following its embedded direction. Numbered files live
in `task/` and are named `instruction_1.md` through `instruction_100.md`.

Each numbered file contains story text and exactly one challenge direction at a
random paragraph boundary, plus 100 decoy directions in each numbered file.
Decoys use the same 100 templates, once each, with random nonnumeric labels
such as “the faded ribbon”; they do not identify a destination. Ignore labels
that do not specify an integer. The start file has no decoys.
Directions use different wording and may identify a
destination using words, numeral bases, arithmetic, equations, units, or counting
clues. Evaluate the label and convert it to a decimal filename: for example,
“half of 24” means `instruction_12.md`. References to bindings, volumes, and
catalog entries all mean numbered sibling files. The final file contains an
explicit stop instruction.

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
| Start-file words | 143 |
| Total words, including start | 10,000,143 |
| Total `cl100k_base` tokens | 12,855,072 |
| Tokens per numbered file | 127,905–129,124 |
| Distinct next-file sentences | 100 |
| Distinct destination encodings | 100 |
| Stop sentences | 1 |
| Decoy sentences per numbered file | 100 |
| Total decoy sentences | 10,000 |

Words are counted with Python's `str.split()` (whitespace-delimited words),
including each file's attribution and direction. [manifest.json](manifest.json)
records measured word/token counts and SHA-256 hashes for every file, in numeric
filename order; it does not record the solution order or a random seed.

The filler is *War and Peace* by Leo Tolstoy, translated by Louise and Aylmer
Maude, from [Project Gutenberg ebook 2600](https://www.gutenberg.org/ebooks/2600).
Project Gutenberg lists this edition as public domain in the USA. Credits:
An Anonymous Volunteer and David Widger. The downloaded text contains 563,286
words between its ebook markers, including its table of contents. The revised corpus samples with replacement from 32,197 sentence units,
removing one randomly selected alphabetic word token from each sampled unit.
Sentence segmentation uses a punctuation heuristic, so abbreviations can split
and headings may remain attached to prose. Each modified unit occupies a paragraph;
the challenge direction and 100 decoys are inserted between units and are not
word-deleted. Their words are included in the fixed word budget.
Sampling near the end of a file is restricted to units that fit the remaining
word budget, preserving exactly 100,000 words without truncating a sampled unit.
The complete extracted list is in `sources/sentences.json` (maintainer data).

The recorded seed is 20261104. Exact sentence matching is disrupted, but approximate
matching and instruction searches remain possible. This is not a guarantee that
a model must read every token. Keep the sentence list, seed, and answer artifacts
outside solver inputs.

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

Generation creates a random 256-bit password in
[`.solution-password`](.solution-password), with owner-only filesystem
permissions at creation. **Check this password file into the repository alongside
the archive**, so a clone includes everything needed to inspect and verify the
answer. The password is intentionally public. Keeping the answer artifacts inside
the ZIP is intended to reduce accidental ingestion of the plaintext solution by
pretraining data pipelines; pipelines that explicitly decrypt the archive can
still read it.

Use an AES-compatible ZIP tool such as 7-Zip to extract the solution. Display the
checked-in password, then enter it when prompted:

```sh
cat .solution-password
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

Verification uses the checked-in `.solution-password` by default. To use a
different password file:

```sh
.venv/bin/python scripts/build_task.py verify --password-file /path/to/password-file
```

It checks all 101 files, their word and token counts and hashes, exactly one
direction per file, 100 decoys with full template coverage per numbered file,
100 distinct transition wordings and 100 distinct number
encodings, a complete traversal with no cycles, an explicit terminal stop, and agreement with both encrypted answer
artifacts. It checks each secret sentence occurs exactly once, matches its file,
and names the expected successor. It also checks AES-256 encryption of both ZIP
members and rejects missing or incorrect passwords. The tests exercise missing
and modified files, a cycle, an incorrect encrypted answer or secret sentence,
password failures, and refusal to overwrite existing artifacts.

To inspect all 100 composed transition phrases without downloading the source,
writing files, or reading the existing challenge, use the standalone debug mode:

```sh
.venv/bin/python scripts/build_task.py --debug-instruction-gen 42
.venv/bin/python scripts/build_task.py --debug-instruction-gen 42 > /tmp/instruction-preview.txt
```

Debug mode requires only the Python standard library; `python3` or `uv run`
can run it without installing the corpus dependencies.

The integer following the option is the seed (zero and negative seeds are also
accepted). Output contains one phrase per line, using every template, number
encoding, and destination once. The same seed reproduces the same preview with
unchanged code and Python runtime; changing it changes the shuffled combinations.
This uses the same composition path as generation, but does not preview the
existing corpus or include its terminal stop sentence. Normal generation retains
its unseeded system randomness. Do not combine this option with `generate` or
`verify`.

To build a fresh challenge, choose a new output directory:

```sh
.venv/bin/python scripts/build_task.py generate --output /tmp/new-reading-trail
```

The generator downloads the source over HTTPS and verifies its pinned checksum.
For an already downloaded copy, add `--source /path/to/pg2600.txt`; the checksum
is still verified. Initial tokenization may also download the `cl100k_base`
encoding data. `--words` changes the word target for a new generation (default:
100,000; minimum 5,000 to fit the decoys and prose). Generation refuses to
overwrite existing challenge artifacts.

Each run chooses a fresh random permutation of 1–100, separately shuffles 100
individually written sentence templates from `scripts/directions.txt`, and
independently shuffles the 100 number encodings in `scripts/number_fuzzer.py`.
Each template and each encoding is used exactly once, with no fixed relationship
between the two. The finite fuzzer covers numeral notation, arithmetic, equations,
counts, and unit conversions for every destination from 1 through 100. It then
randomly places one composed direction and 100 decoys into each numbered story
chunk. The real direction and decoys share the same placement mechanism; no
special position identifies the real direction. The terminal file also receives
100 decoys alongside its stop sentence. Decoys increase keyword matches, but a
parser that understands the number encodings can still filter them out.

Unlike the previous four target formats, these directions have no shared
`instruction file` phrase or literal filename. This defeats the previous simple
keyword extractor, not arbitrary programmatic solving. The maintainer verifier
knows the grammar and can still parse every combination; do not provide generator
code to solvers. Tests cover all 10,000 number/encoding pairs and all 10,000
template/encoding pairs, including boundary values.

The start file points to the first shuffled number; 99 numbered files
point to their successors, and the remaining file ends the trail. It saves the
encrypted answer and secret sentences, password file, source terms, and
manifest, then validates the result. No seed or plaintext answer artifact is saved.
Regenerated challenges have
different answers and measured token totals; update the table above if replacing
the checked-in corpus.

## Regenerate randomized sentence corpus

```sh
python3 scripts/randomize_corpus.py --seed 20261104 --output /tmp/randomized-trail
```

Install `requirements.txt` first. The output directory must not already exist.
The script downloads and checksum-verifies the novel; `--source /path/to/pg2600.txt`
uses a local copy instead. `--root` selects the existing trail to preserve.
The same seed, source, trail, and Python runtime reproduce task text and metadata.
The ZIP uses fresh encryption randomness, so its bytes need not be identical.
The script writes the sentence list, all task files, manifest, password and updated
AES ZIP, then runs the full verifier. The original `build_task.py generate` command
still produces the older continuous-prose variant; use this script for random sampling.

To replace both the trail and the sampled prose, first generate into a fresh
staging directory, then run `randomize_corpus.py --root` against that directory
with another fresh output directory. Validate the final result before copying
its task files, manifest, source artifacts, password, and ZIP into the repository.
