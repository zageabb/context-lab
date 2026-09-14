# Context Lab

## Ubuntu server deployment

Verified on **14 September 2026** against the listeners, user systemd services,
Docker port mappings and deployment registry on `192.168.1.249`.

| Endpoint | Host TCP port | LAN URL |
|---|---:|---|
| Application | 5051 | http://192.168.1.249:5051/ |

Checkout: `/home/zageabb/ollama-chat/context-lab`.

These are **user** systemd units. Inspect them with:

```bash
systemctl --user status ollama-chat-context-lab.service
systemctl --user cat ollama-chat-context-lab.service
```

Local verification URL: `http://127.0.0.1:5051/`. HTTP 200 was observed during this audit.

Development defaults and container-internal ports elsewhere in this repository
may differ from this host deployment. Use the live ports above when accessing
this Ubuntu server; do not start a second copy on a port already occupied.

[Complete Ubuntu port inventory](https://github.com/zageabb/universal-deployment-agent/blob/main/UBUNTU_PORTS.md).

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
