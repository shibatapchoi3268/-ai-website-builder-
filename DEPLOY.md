# Deploy the research chat

The Streamlit app is `web_builder.py`. It provides a Gemini-powered chat and
uses Gemini's native Google Search grounding for web research and source links.
Each visitor enters their own Gemini API key; no key is needed in Streamlit
Cloud's Secrets. The key is sent to this app's server for the request and
forwarded to Google. Use only a deployment you trust.

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository for this project and push the project files.
   Do not commit API keys, `.env` files, or `.streamlit/secrets.toml`.
2. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) with
   GitHub and choose **Create app**.
3. Select the repository and branch, set **Main file path** to `web_builder.py`,
   then deploy.
4. Open the deployed app URL. Visitors enter their Gemini API key in the
   sidebar, then ask questions in the chat.

Dependencies are installed from `requirements.txt`. The MCP server is a
separate local integration; it is not required to use the deployed Streamlit
app. The chat retries a temporary Gemini 503 once, then tries Gemini 3.6 Flash
if Gemini 3.8 Flash remains unavailable.

The source code is public in the selected GitHub repository. Publishing the
running app still requires signing in to Streamlit Community Cloud and creating
the app there.

## Deploy a local project to SFTP hosting

The Streamlit Cloud app cannot read files from your PC or connect with local
credentials. Run the SFTP helper on your own computer instead:

Prepare a local website project folder containing its `index.html` and any
required CSS, JavaScript, or asset files, then run:

```powershell
python -m pip install -r requirements-sftp.txt
python -m services.sftp_deployer "C:\path\to\your\website"
```

The helper prompts for the SFTP host, account, authentication method, and remote
directory (defaults to `/public_html`). It accepts a password or a private-key
file; credentials are prompted locally and are not written to the project.
Before uploading, it lists the files and overwrites, backs up overwritten
remote files under `%USERPROFILE%\.ai_website_builder\deploy_backups`, and
requires you to type `DEPLOY`. It never deletes remote files that are absent
from the local project.

For SSH host verification, the server must already be in your local
`known_hosts` file. Verify the hosting provider's SSH fingerprint before
trusting a new host; do not disable host-key checking. The helper excludes
`.env` files, private-key files, Git metadata, virtual environments, and
dependency directories. It uploads files only; build the project locally first
if it requires a build step.
