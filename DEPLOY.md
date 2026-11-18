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
