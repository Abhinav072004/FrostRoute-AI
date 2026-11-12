# Deploy FrostRoute AI to Streamlit Community Cloud

The demo uses historical CSV data and local vectorless SOP retrieval. It needs no API keys, Pinecone, SQL Server, or `.env` file. Conversational AI is disabled in the demo until a provider is configured.

## Deploy

1. Visit https://share.streamlit.io/ and sign in with GitHub. Authorize access to `Abhinav072004/FrostRoute-AI` if requested.
2. Choose **Create app** (or **New app**), then deploy from an existing GitHub repository.
3. Set **Repository** to `Abhinav072004/FrostRoute-AI`, **Branch** to `main`, and **Main file path** to `src/ui.py`.
4. Open **Advanced settings** and choose **Python 3.12**. Leave secrets empty for the default demo. If you have previously configured this app, remove stale service settings before testing the demo.
5. Choose an available app URL and click **Deploy**. URL availability and successful deployment must be verified in your Streamlit account; no URL is reserved by this repository.
6. Test **Load fleet sample**, SOP search, and the confirmed-cargo temperature checker. The Assistant tab should explain that conversational AI requires configuration.
7. Review the app's sharing settings. Keep it restricted if you do not want a public portfolio demo. App sharing and GitHub repository visibility are separate settings.

`src/requirements.txt` includes the tested root dependency lock. `packages.txt` supplies the ODBC shared library for the optional Python driver; it does not install Microsoft's ODBC Driver 18 or provision SQL Server. Do not use the EC2 GitHub Actions workflow for Community Cloud.

## Optional AI configuration

To enable hosted AI later, use the host's secret settings, never GitHub files or chat messages. Verify the provider integration separately and add authentication and request/cost limits before exposing paid AI to untrusted visitors. The demo does not require these credentials.

## Hosting limits

Audit files under `.runtime/` and conversation memory are local to the running instance. Restarts, redeploys or host storage changes may remove them. Do not use this demo as a durable production audit system. The audit viewer is disabled unless its password is configured. The app never executes dispatch actions.

## Troubleshooting

- Dependency error: confirm Python 3.12 and inspect the build logs.
- File not found: confirm repository `main` and entrypoint `src/ui.py`.
- Database/API error in the demo: check for old environment or secrets settings; the intended demo uses `DATA_BACKEND=demo`, `RAG_BACKEND=local`, `AGENT_LLM=DEMO`.
- Restricted app access: sign in as the account owner and review sharing settings.

A running local preview or a successful GitHub push is not a verified Community Cloud deployment. Streamlit must report the app running and supply its actual URL.
