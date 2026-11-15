# How to use this kit

This folder has everything you need to get an LLM to write a question bank you can import into Self-Test.

| File | What it's for |
|---|---|
| `QUESTION_WRITING_GUIDE.md` | The rules for the LLM: research, topic planning, CSV format and question quality. |
| `sample_question_bank.csv` | A complete, valid example bank that the LLM copies the format from. |
| `PROMPT INSTRUCTION.md` | The prompt to paste, with blanks to fill in. |
| `HOW TO USE.md` | This file. You don't need to give it to the LLM. |

## Steps

1. **Fill in the prompt.** Open `PROMPT INSTRUCTION.md`, replace *[Topic / Exam Name]* with the subject or exam, and change the question counts if you want more or fewer. If you have a link to the syllabus, add it after the exam name: it makes the topics much better.
2. **Give the LLM three things:** the filled-in prompt, `QUESTION_WRITING_GUIDE.md` and `sample_question_bank.csv`. Use an LLM with web search if you can, so it can research and check facts.
3. **Review the plan.** The LLM replies first with its modules, knowledge points and question counts. Ask for changes until you're happy, then tell it the plan is approved and to write the CSV.
4. **Save the CSV reply as a `.csv` file.** Copy only the CSV, starting at the `module,knowledge_point,…` header. If the LLM wrapped it in a Markdown code block (```` ``` ````), leave out those fence lines. Save it as UTF-8.
5. **Import it.** In Self-Test, go to **Import**, choose an existing bank or type a name for a new one, pick the file, keep **"Skip questions whose text is already in the bank"** ticked, and press **Import**. Modules and knowledge points are created automatically.
6. **Fix any rejected rows.** The import result lists problem rows by line number. Ask the LLM to fix those lines (paste it the error messages), or fix them yourself in a text editor or spreadsheet. Then import the same file again: questions that already went in are skipped, so only the fixed rows are added.
7. **Check the result.** Open the bank's **Modules** page to make sure the topics look right (you can rename and reorder them there), and spot-check a few questions on the **Questions** page.

## Tips

- **Large banks:** ask for 30 to 50 questions at a time, one module per request, and import each file into the same bank. Remind the LLM of the module and knowledge-point names it already used, so they stay spelled the same.
- **Review the facts.** The guide tells the LLM to verify everything, but LLMs still make mistakes. If an answer looks wrong while you practise, fix it on the bank's Questions page.
- **Spreadsheets:** if you edit the CSV in Excel or a similar program, save it as "CSV UTF-8" so special characters survive.
