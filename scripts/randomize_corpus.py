#!/usr/bin/env python3
"""Rebuild a trail with seeded, word-deleted random sentence samples."""
import argparse
import json
import random
import re
from pathlib import Path
from urllib.request import urlopen

import pyzipper
import tiktoken
import build_task as task


def split_sentences(body):
    """Heuristic segmentation: terminal punctuation followed by whitespace.

    Abbreviations may split; headings remain attached to surrounding prose.
    Keep only units with at least two whitespace-delimited words containing letters.
    """
    normalized = re.sub(r'\s+', ' ', body).strip()
    pieces = re.split(r'(?<=[.!?])\s+|(?<=[.!?][”\"])\s+', normalized)
    return [s for s in pieces if sum(any(c.isalpha() for c in w) for w in s.split()) >= 2]


def sample_prose(sentences, budget, rng):
    buckets = {}
    for sentence in sentences:
        words = sentence.split()
        buckets.setdefault(len(words) - 1, []).append(words)
    if 1 not in buckets:
        raise ValueError('Need a two-word source sentence to fill exact word budgets.')
    result = []
    while budget:
        # Uniform selection among all sentences that fit the remaining budget.
        eligible = [words for size, group in buckets.items() if size <= budget for words in group] if budget < max(buckets) else None
        words = (rng.choice(eligible) if eligible is not None else rng.choice(sentences).split()).copy()
        indices = [i for i, w in enumerate(words) if any(c.isalpha() for c in w)]
        del words[rng.choice(indices)]
        budget -= len(words)
        result.append(' '.join(words))
    return result


def rebuild(root, output, source, seed):
    if task.digest(source) != task.SOURCE_SHA256:
        raise ValueError('Source checksum mismatch.')
    if output.exists():
        raise ValueError('Choose a new output directory.')
    text = source.decode('utf-8-sig').replace('\r\n', '\n')
    front, rest = text.split(task.START_MARKER, 1)
    body, back = rest.split(task.END_MARKER, 1)
    sentences = split_sentences(body)
    password = (root / '.solution-password').read_text().strip()
    with pyzipper.AESZipFile(root / 'solution/solution.zip') as archive:
        names = archive.read('solution.txt', pwd=password.encode()).decode().splitlines()
        evidence = json.loads(archive.read('secret_sentences.json', pwd=password.encode()))
    rng = random.Random(seed)
    for directory in ('task', 'sources', 'solution'):
        (output / directory).mkdir(parents=True, exist_ok=True)
    (output / 'sources/sentences.json').write_text(json.dumps(sentences, ensure_ascii=False, indent=2)+'\n')
    (output / 'sources/gutenberg-license.txt').write_text('\n'.join(line.rstrip() for line in (front + back).splitlines()).rstrip() + '\n')
    original = json.loads((root / 'manifest.json').read_text())
    target = original['words_per_numbered_file']
    encoder = tiktoken.get_encoding('cl100k_base')
    records = {}
    header = task.HEADER.replace('repeated, split, and interspersed', 'randomly sampled, word-deleted, and interspersed')
    for name in ['start_instruction.md'] + [task.filename(n) for n in range(1, 101)]:
        direction = evidence[name]['sentence']
        if name == 'start_instruction.md':
            content = task.START + direction + '\n'
        else:
            insertions = [direction] + task.generate_decoys(rng)
            budget = target - len(header.split()) - sum(len(s.split()) for s in insertions)
            if budget <= 0:
                raise ValueError('Word budget cannot fit 100 decoys and prose.')
            prose = task.intersperse(sample_prose(sentences, budget, rng), insertions, rng)
            content = header + '\n\n'.join(prose) + '\n'
            assert len(content.split()) == target
        data = content.encode()
        (output / 'task' / name).write_bytes(data)
        records[name] = dict(words=len(content.split()), tokens=len(encoder.encode_ordinary(content)), sha256=task.digest(data))
    manifest = {k:v for k,v in original.items() if k not in ('source_passes', 'prose_words_used', 'files')}
    manifest.update(decoys_per_numbered_file=task.DECOYS_PER_FILE, files=records, total_words=sum(r['words'] for r in records.values()), total_tokens=sum(r['tokens'] for r in records.values()), sampling_seed=seed, source_sentences=len(sentences), sampling='with replacement; one alphabetic word token removed per sample', sentence_segmentation='terminal punctuation heuristic v1')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    task.write_private(output / '.solution-password', password+'\n')
    task.write_solution(output, names, {n:e['sentence'] for n,e in evidence.items()}, password)
    task.verify(output, output / '.solution-password')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--root', type=Path, default=task.ROOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    source = args.source.read_bytes() if args.source else urlopen(task.SOURCE_URL, timeout=60).read()
    result = rebuild(args.root, args.output, source, args.seed)
    print(f"Validated {len(result['files'])} files; {result['source_sentences']} source sentences; {result['total_tokens']} tokens.")
