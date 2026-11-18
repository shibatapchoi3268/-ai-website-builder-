# Deploy the website app

The Streamlit app is `web_builder.py`. It asks each visitor for their own AI
provider and API key; no provider key is needed in Streamlit Cloud's Secrets.
The key is sent to this app's server for the request and forwarded to the
selected AI provider. Use only a deployment you trust.

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository for this project and push the project files.
   Do not commit API keys, `.env` files, or `.streamlit/secrets.toml`.
2. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) with
   GitHub and choose **Create app**.
3. Select the repository and branch, set **Main file path** to `web_builder.py`,
   then deploy.
4. Open the deployed app URL. Visitors select their AI provider and enter their
   own API key in the sidebar.

Dependencies are installed from `requirements.txt`. The MCP server is a
separate local integration; it is not required to use the deployed Streamlit
website.

The source code is public in the selected GitHub repository. Publishing the
running app still requires signing in to Streamlit Community Cloud and creating
the app there.

## Deploy a local project to SFTP hosting

The Streamlit Cloud app cannot read files from your PC or connect with local
credentials. Run the SFTP helper on your own computer instead:

Download the generated `index.html` from the web app and place it in a local
project folder. Add any CSS, JavaScript, or asset files that project needs to
that folder, then run:

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
