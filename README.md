The following is the task that would force any ai agent solving it consuming 2
million tokens total.

The task is structure at follow:

The task/ folder in this repo has 101 files named `start_instruction.md`,
`instruction_1.md`, `instruction_2.md`,..

The `start_instruction.md` ask the agent to read the next `instruction_{i}.md`
file and follow the next read file read instruction. The agent would need to
keep following this sequence:

* Read `start_instruction.md` file fully to file the next
`instruction_i.md` file to read.
* Read `instruction_i.md` file fully to file the next `instruction_j` file to
read.
* .. so on and so forth.

At the end, the agent need to be able to output solution.txt in which it states
the correct sequence of all instruction files as follow

```
start_instruction.md
instruction_45.md
instruction_17.md
...
```
(note that the content above is only for illustration, the exact solution may
not be this)

Every instruction file has 200K token of meaningful text, with one exact sentence
that instructs the agent what is the next instruction file it should read. To
prevent the agent from cheating by using regex/Python code to scan for the next
file instruction from these files without reading the full file, the instruction
line in each file would be different, while semantically sufficient that if the
agent read the full file from top to bottom, it would be able to find out the next
`instruction_*.md` file.

the solution/ folder in this repo contain solution.tar.gz file that once extract
contain the correct solution text.
