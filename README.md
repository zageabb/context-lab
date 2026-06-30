# Context Lab

Context Lab is a simplified Flask app extracted from the local Tender Designer work and reshaped for one job:
testing how different document context and prompt instructions affect LLM chat answers.

## What it includes

- Persistent saved environments
- Per-environment copied instruction files that can diverge between experiments
- Document upload and text extraction for `pdf`, `docx`, `xlsx`, `txt`, `csv`, and `eml`
- Automatic chunking of processed documents for lightweight RAG retrieval
- Checkbox-based document selection for chat context experiments
- Environment-scoped chat history
- Global settings for Ollama and chunking defaults

## Structure

- `app.py`: Flask entry point
- `models.py`: environments, documents, prompts, chunks, settings, and chat tables
- `routes/`: dashboard, environments, settings, and chat endpoints
- `services/`: extraction, prompt copying, retrieval, storage, settings, and Ollama client
- `templates/` and `static/`: copied and adapted Tender Designer UI shell

## Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the app:

```bash
python app.py
```

3. Open:

`http://127.0.0.1:5051`

## Notes

- The default Ollama URL and model names are seeded from the original Tender Designer settings and can be changed in the Settings page.
- Each new environment gets its own prompt files copied into `data/environments/<id>/prompts/`.
- Chat retrieval is intentionally simple and transparent so it is easier to test context effects without hiding behaviour behind a heavier vector stack.
