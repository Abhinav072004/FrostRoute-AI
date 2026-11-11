# Start here

1. Extract the ZIP fully. Open the extracted `FrostRoute-AI-main` (or `FrostRoute-AI` after cloning) folder in VS Code.
2. Install Python 3.12 and the recommended Python extension.
3. Follow the Windows or macOS/Linux commands in `README.md` to create `.venv`, install dependencies, and copy `.env.example` to `.env`.
4. Run `streamlit run src/ui.py`. The default historical-data demo requires no API keys.
5. Open Evidence explorer to load fleet observations, search SOP passages, and check a confirmed fresh-perishable observation.
6. For AI conversation, configure a supported provider in `.env` as explained in `README.md` and restart.
7. Run `python -m unittest discover -s tests -v` before pushing. VS Code also offers **Run Test Task** after selecting your virtual environment interpreter.
8. Configure real service credentials only when enabling the optional integrations; see `README.md`.

`docs/REVIEW.md` describes implemented fixes, tests and remaining integration limits. `.vscode/launch.json` lets you launch Streamlit using **Run and Debug** after selecting the virtual environment interpreter.

The archive excludes local credentials, environments, audit databases and generated caches. `PACKAGE_MANIFEST.json` lists the SHA-256 of every shipped project file except the manifest itself. Reference PDFs and dataset source information are retained. Do not present the historical sample as live shipment data.
