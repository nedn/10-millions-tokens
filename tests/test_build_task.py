import json
import tempfile
import unittest
from pathlib import Path

import pyzipper
import tiktoken

from scripts import build_task as task


class ReadingTrailTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.password = self.root / ".solution-password"
        # A small offline fixture exercises the same 100-file graph and archive.
        source = (task.START_MARKER + "\n\n" +
                  "The traveler crossed the bridge and watched the river below.\n\n" +
                  "At sunset the village grew quiet and the lamps were lit.\n\n" +
                  task.END_MARKER).encode()
        task.build(self.root, source, words=250)

    def test_complete_trail_and_encrypted_archive(self):
        result = task.verify(self.root, self.password)
        self.assertEqual(len(result["files"]), 101)
        self.assertTrue(all(v["words"] == 250 for k, v in result["files"].items()
                            if k != "start_instruction.md"))
        self.assertFalse(list(self.root.rglob("solution.txt")))
        self.assertFalse(list(self.root.rglob("secret_sentences.json")))
        self.assertEqual(self.password.stat().st_mode & 0o777, 0o600)

    def test_existing_challenge_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError, "already contains"):
            task.build(self.root, b"unused", words=250)

    def test_missing_file_is_rejected(self):
        (self.root / "task/instruction_1.md").unlink()
        with self.assertRaisesRegex(ValueError, "exactly one start"):
            task.verify(self.root, self.password)

    def test_modified_story_is_rejected(self):
        with (self.root / "task/instruction_1.md").open("a") as handle:
            handle.write("Unexpected additional text.\n")
        with self.assertRaisesRegex(ValueError, "Content or count mismatch"):
            task.verify(self.root, self.password)

    def test_wrong_password_is_rejected(self):
        wrong = self.root / "wrong-password"
        wrong.write_text("wrong")
        with self.assertRaises(RuntimeError):
            task.verify(self.root, wrong)

    def test_encrypted_but_incorrect_answer_is_rejected(self):
        with pyzipper.AESZipFile(self.root / "solution/solution.zip") as archive:
            evidence = archive.read("secret_sentences.json", pwd=self.password.read_bytes().strip())
        with pyzipper.AESZipFile(self.root / "solution/solution.zip", "w",
                                encryption=pyzipper.WZ_AES) as archive:
            archive.setpassword(self.password.read_bytes().strip())
            archive.setencryption(pyzipper.WZ_AES, nbits=256)
            archive.writestr("solution.txt", "start_instruction.md\n")
            archive.writestr("secret_sentences.json", evidence)
        with self.assertRaisesRegex(ValueError, "does not match"):
            task.verify(self.root, self.password)

    def test_incorrect_secret_sentence_is_rejected(self):
        with pyzipper.AESZipFile(self.root / "solution/solution.zip") as archive:
            password = self.password.read_bytes().strip()
            answer = archive.read("solution.txt", pwd=password)
            evidence = json.loads(archive.read("secret_sentences.json", pwd=password))
        evidence["instruction_1.md"]["sentence"] = "A sentence that is not in the file."
        with pyzipper.AESZipFile(self.root / "solution/solution.zip", "w",
                                encryption=pyzipper.WZ_AES) as archive:
            archive.setpassword(password)
            archive.setencryption(pyzipper.WZ_AES, nbits=256)
            archive.writestr("solution.txt", answer)
            archive.writestr("secret_sentences.json", json.dumps(evidence))
        with self.assertRaisesRegex(ValueError, "secret sentences do not match"):
            task.verify(self.root, self.password)

    def test_cycle_is_rejected_even_with_updated_checksums(self):
        parse = task.direction_parser()
        for number in range(1, 101):
            name = task.filename(number)
            path = self.root / "task" / name
            content = path.read_text()
            matches = [p for p in content.split("\n\n") if parse(p.strip())]
            if matches:
                old = matches[0].strip()
                _, template, style = parse(old)
                replacement = task.direction(template, number, style)
                # Choose a replacement that preserves the fixed word budget.
                if len(replacement.split()) != len(old.split()):
                    continue
                content = content.replace(old, replacement)
                path.write_text(content)
                manifest_path = self.root / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                record = manifest["files"][name]
                tokens = len(tiktoken.get_encoding("cl100k_base").encode_ordinary(content))
                manifest["total_tokens"] += tokens - record["tokens"]
                record.update(tokens=tokens, sha256=task.digest(path.read_bytes()))
                manifest_path.write_text(json.dumps(manifest))
                break
        else:
            self.fail("No suitable transition found")
        with self.assertRaisesRegex(ValueError, "cycle"):
            task.verify(self.root, self.password)


if __name__ == "__main__":
    unittest.main()
