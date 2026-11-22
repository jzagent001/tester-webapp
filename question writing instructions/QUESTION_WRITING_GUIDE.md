# How to write a question bank for Self-Test

This guide is for an LLM (or a person) writing a question bank that the Self-Test app can import. `sample_question_bank.csv` in this folder is a complete, valid example: refer to its structure. Rows that break the rules below are rejected on import.

The work has four steps: research the subject, plan the topics, write the questions, check the file.

## 1. Research the subject

- **Start from the official scope.** Find the exam syllabus, blueprint, course outline or certification guide. It tells you what to cover and how much: if a section is 30% of the exam, give it about 30% of the questions.
- **Take facts from primary sources:** standards (RFCs, ITU, IEEE, ISO), official vendor documentation, textbooks and official training material. Use blogs, forums and videos only to find topics and common misunderstandings, then confirm the facts in a primary source.
- **Note the version.** Products and standards change. When an answer depends on a version, say which in the question ("In TLS 1.3, …").
- **Collect misconceptions as you go.** Forum questions, errata and "common pitfalls" sections show what learners get wrong, and those make the best wrong answers.
- **Don't trust question dumps.** Their answers are often wrong and can't be checked.
- **If you can't verify a fact, leave the question out.** Never invent numbers, defaults or version details.

## 2. Plan modules and knowledge points

A bank has up to two levels, and test results are scored per module and per knowledge point:

- **module**: a broad area, e.g. `DNS`. Use the syllabus sections.
- **knowledge point**: a specific topic inside a module, e.g. `Record types`. Use the syllabus objectives.

Decide the full list before writing, and then spell every name exactly the same way each time (`Record types` and `DNS record types` would become two different knowledge points). Keep names short. Plan for **at least 3 questions per knowledge point**, preferably 5 or more.

## 3. Write the CSV

Use exactly this header, always with all eight choice columns:

```
module,knowledge_point,question,A,B,C,D,E,F,G,H,correct,explanation
```

| Column | Required | Content |
|---|---|---|
| `module` | no | Module name. |
| `knowledge_point` | no | Knowledge point name. Needs a module. |
| `question` | yes | The question text. |
| `A`–`H` | `A` and `B` | 2 to 8 answer choices, filled from `A` with no gaps. Leave unused columns empty. |
| `correct` | yes | Letter(s) of every correct choice, separated by `;`, e.g. `B` or `A;C`. |
| `explanation` | always write one | Shown after the user answers. |

**Classification:** fill both `module` and `knowledge_point` for a specific topic, `module` only for a general question about that module, or neither for a general question about the whole bank. Use the most specific level that fits.

**CSV rules:**

- Wrap any field containing a comma in double quotes: `"slow, salted hashes"`.
- Inside a quoted field, write a double quote twice: `"the hostname ""localhost"""`.
- One question per line, no line breaks inside fields, no blank or comment lines.
- Every row has 13 fields. A four-choice row ends `…,D-text,,,,,A,"explanation"`.
- Save as UTF-8.

## 4. Write good questions

The app **shuffles the choices** in every test and tells the user how many to pick when a question has more than one correct answer. So:

- Never write "all of the above", "none of the above" or "both A and C", and don't let choice order hint at the answer.
- Don't add "(select two)" to the question text. The app adds that itself.
- Make every question's wording unique. Repeated text counts as a duplicate on import.

**Questions:** test one idea each. Someone who knows the topic should be able to answer before reading the choices. Prefer applied scenarios over bare definitions, mix the difficulty, and avoid negatives and trick wording.

**Choices:** use 4 by default, 2 only for true/false, and up to 8 when the topic has that many natural options. Every wrong choice should be plausible: a common misconception, a related term or a realistic miscalculation. Make sure exactly the marked ones are correct.

**Don't let the wording give the answer away.** The most common giveaway is that the correct choice is the longest, because it collects the qualifiers that make it precisely true while the wrong choices are written quickly. Write the correct choice first, then make each wrong choice about as long and as specific: if the correct one has a qualifier, a number or a condition, give the wrong ones a qualifier, a number or a condition too. Trimming the correct choice works as well. Don't overcorrect: if the correct choice is never the longest, that is a giveaway too. Across the bank, the correct choice should be the longest about as often as chance (about 1 in 4 questions with four choices). Also watch for these:

- Only the correct choice hedges ("usually", "typically") while the wrong ones say "always" or "never".
- Only the correct choice repeats words from the question.
- Only the correct choice is a full, careful sentence while the others are fragments.

When the choices are names or values whose length is fixed (status codes, record types, port numbers), length tells the reader nothing, so don't bend them to fit.

**Explanations:** 1 to 3 sentences that say why the answer is right and why the main wrong choices are wrong. Name the source when it helps (e.g. "RFC 9110").

## Checklist

- [ ] Header matches exactly, and every row has 13 fields with correct quoting.
- [ ] Every row has a question, choices `A` and `B`, and correct letters that point to non-empty choices.
- [ ] No knowledge point without a module, and every name is spelled consistently.
- [ ] No choice refers to other choices.
- [ ] For each question, note which choice is longest. The correct choice is the longest in about 1 in 4 questions, not much more or less; where it is clearly longer than the rest, trim it or lengthen the wrong ones.
- [ ] Every question has an explanation, and every fact was checked against a source.
- [ ] Each knowledge point has at least 3 questions.
- [ ] The output is only the CSV: no Markdown fences, no notes before or after.
