# How to write a question bank for Self-Test

This guide is written for an LLM (or a person) producing a question bank that the Self-Test
app can import. Follow it exactly: the importer rejects rows that break the rules and reports
them by line number.

The companion file `sample_question_bank.csv` in this folder is a complete, valid example.
Copy its structure.

## What you are producing

One **CSV file**, UTF-8 encoded, with a header row followed by one row per question. Every
question is multiple choice, with 2 to 8 answer choices and one or more correct answers.

A bank is organised in up to two levels:

- **module**: a broad area of the subject (e.g. `DNS`)
- **knowledge point**: a specific topic inside a module (e.g. `Record types`)

After a test the app scores the user per module and per knowledge point, so good
classification is what makes the results useful.

## The header

Use exactly this header, in this order:

```
module,knowledge_point,question,A,B,C,D,E,F,G,H,correct,explanation
```

Always include all eight choice columns `A`–`H`, even if every question uses only four. Leave
the unused ones empty.

## Columns

| Column | Required | What goes in it |
|---|---|---|
| `module` | no | Module name. Blank = a general question for the whole bank. |
| `knowledge_point` | no | Knowledge point name, inside the module. Blank = a general question within the module. **Needs a module**: a knowledge point with a blank module is an error. |
| `question` | **yes** | The question text. |
| `A`–`H` | `A` and `B` required | Answer choices, filled from `A` onwards with no gaps. Leave unused columns empty. |
| `correct` | **yes** | The letter of every correct choice, in capitals, separated by `;`. Examples: `B`, `A;C`, `A;B;D`. Each letter must point at a non-empty choice. |
| `explanation` | no, but always write one | Shown to the user after they answer. |

### The three ways to classify a question

| module | knowledge_point | Meaning | Sample row |
|---|---|---|---|
| `DNS` | `Record types` | A specific knowledge point | the AAAA record question |
| `HTTP` | *(blank)* | General question for the module | the HTTP/2 question |
| *(blank)* | *(blank)* | General question for the whole bank | the HTTPS port question |

Prefer the most specific level that fits. Use the general levels only for questions that
genuinely span topics.

## CSV rules that trip people up

1. **Quote any field that contains a comma** by wrapping it in double quotes:
   `"Hash them with a slow, purpose-built algorithm such as bcrypt or Argon2"`.
2. **A double quote inside a quoted field is written twice**:
   `"True or false: the hostname ""localhost"" resolves to 127.0.0.1."`
3. **One question per line.** Don't put line breaks inside any field.
4. Every row has the same number of columns as the header (13). Count the commas for the
   empty choice columns: a four-choice question ends `...,D-text,,,,,A,"explanation"`.
5. Save as UTF-8. Characters such as `–`, `›`, `é` and `µ` are fine.
6. No blank lines between rows and no comment lines. Output nothing except the header and
   the question rows.

## Naming modules and knowledge points

- Pick the module and knowledge-point names **before** writing questions, and reuse them
  **exactly**. Names are matched without regard to case or extra spaces, so `Record types`
  and `record  TYPES` count as the same, but `Record types` and `DNS record types` become
  two separate knowledge points.
- Keep names short (1–5 words) and in title or sentence case: `Status codes`, not
  `HTTP status codes (3xx/4xx/5xx)`.
- Each knowledge point belongs to one module. The same knowledge-point name under two
  modules is two different knowledge points.
- When the bank follows an exam, mirror the exam's published syllabus: its sections become
  modules and its objectives become knowledge points.
- Aim for **at least 3 questions per knowledge point**, and preferably 5 or more. The app
  only lists a topic among the user's weakest topics once it has 3 answers.

## How the app treats your questions (so write for it)

- **Choices are shuffled in every test.** The letters the user sees don't match your
  columns. So:
  - Never write "All of the above", "None of the above", "Both A and C" or anything else that
    refers to other choices by position or letter.
  - Don't rely on choice order, e.g. lists in ascending order that hint at the answer.
- **Multiple correct answers** turn the question into checkboxes, and the app tells the user
  how many to pick ("Choose 3."). The user must select exactly the correct set to score.
  Don't write "(select two)" in the question text; the app adds that for you.
- **One correct answer** shows radio buttons.
- **Duplicates**: on import, a question whose text matches one already in the bank (ignoring
  case and spacing) can be skipped. Make every question's wording distinct.
- **The explanation appears right after answering**, next to the user's answer and the correct
  one.

## Writing good questions

**The question**

- Test one idea per question. If you need "and" to describe what it tests, split it.
- Make it answerable without the choices: a reader who knows the topic should be able to
  predict the answer before reading them.
- Prefer applied questions ("A page has moved permanently. Which status code…?") over bare
  definitions, and mix difficulty levels.
- Avoid negatives ("Which is NOT…"). If you must use one, put NOT in capitals.
- Avoid trick wording, double negatives and ambiguity. The challenge should come from the
  subject, not from parsing the sentence.

**The choices**

- Give 4 choices by default. Use more (up to 8) when the topic naturally has that many
  options, e.g. port numbers. Use exactly 2 only for true/false.
- Every wrong choice (distractor) should be plausible: a common misconception, a related
  term or a near-miss value. Avoid joke answers.
- Keep all choices similar in length, grammar and detail. The correct answer shouldn't stand
  out by being longest or most precise.
- Choices must not overlap. Exactly the listed correct choices are right and every other choice
  is clearly wrong.
- For numeric answers, base the distractors on realistic mistakes (wrong unit, off by a factor
  of 10, a dB value treated as a linear one).

**The explanation**

- Say why the correct answer is correct, then briefly why the main distractors are wrong.
  The sample file shows the expected depth: 1 to 3 sentences.
- Cite a standard or source by name when one is useful (e.g. "RFC 9110").

**Accuracy and originality**

- Every fact must be correct. When unsure, leave the question out rather than guess.
- Write original questions. Don't reproduce questions from real exams, braindumps or
  copyrighted question banks.

## Checklist before you output

- [ ] Header is exactly `module,knowledge_point,question,A,B,C,D,E,F,G,H,correct,explanation`.
- [ ] Every row has 13 fields; fields containing commas or quotes are quoted correctly.
- [ ] Every row has question text, choices `A` and `B`, and at least one correct letter.
- [ ] Every letter in `correct` points to a non-empty choice; choices have no gaps.
- [ ] No row has a knowledge point without a module.
- [ ] Module and knowledge-point names are spelled identically everywhere.
- [ ] No choice refers to another choice ("all of the above", "A and B").
- [ ] Every question has an explanation.
- [ ] Each knowledge point has at least 3 questions.
- [ ] Nothing is in the output except CSV: no Markdown fences in the saved file, no notes
      before or after.

## Prompt template

Paste this to an LLM together with this guide and the sample file:

> Using the attached guide and `sample_question_bank.csv` as the format reference, write a
> question bank for **[subject / exam name]**. First list the modules and knowledge points
> you will use (based on **[syllabus or scope, if any]**). Then write **[N]** questions,
> at least **[3–5]** per knowledge point, with a mix of single- and multiple-answer
> questions and a mix of difficulty. Output only the CSV, starting with the header row.

## Importing

In the app, go to **Import**, choose an existing bank or type a name for a new one, pick the
CSV file and press **Import**. Modules and knowledge points that don't exist yet are created
automatically. Rows with problems are listed by line number and skipped; fix them and
import the file again with "Skip questions whose text is already in the bank" ticked.
