# Aomail Web Application
Open source automated email management tool.

Our discord server: https://discord.com/invite/JxbPZNDd (under construction)

Features:
- **Replication on provider**: labels on Gmail & Outlook 
- **Auto categorize emails**: with labels and categories and your own rules
- **Compose and reply to emails**: with AI chat assistant
- **AI short summary of emails**: with AI chat assistant
- **Analytics**: see how your emails are being used
- **Link multiple email accounts**: link multiple accounts to the same account

Under development:
- **AI Custom rules**: automatic forward, and smart reply with AI
- **Discord & Slack integration**: Summary of immportant emails + what happened since last connection
- **LLM choice**: support for other LLMs and choice in settings (OpenAI, Anthropic, Llama, Mistral)



## Getting started with self-hosting

Disclaimer:
We have tested the app with WSL 2 and Docker Desktop. As well as within a Debian server.
It might work on other platforms, but we have not tested it.

External services:
- Gemini 
- Google OAuth
- Google PubSub
Optional services:
- Stripe
- Microsoft Azure

 
```bash
git clone https://github.com/aomail-ai/aomail-app
cd aomail-app
cd frontend && npm install
cd .. && cp backend/.env.example backend/.env
```
Fill the .env file with your API keys and secrets.

required environment variables:
# todo: putt all links to generate keys
GEMINI_API_KEY
for encryption keys: use ```python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'``` to generate a key 
    SOCIAL_API_REFRESH_TOKEN_KEY
    EMAIL_ONE_LINE_SUMMARY_KEY
    EMAIL_SHORT_SUMMARY_KEY
    EMAIL_HTML_CONTENT_KEY
DJANGO_SECRET_KEY
DJANGO_DB_USER
DJANGO_DB_PASSWORD

If you are using Gmail setup
GOOGLE_TOPIC_NAME
GOOGLE_PROJECT_ID
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET

If you are using Microsoft Azure setup
MICROSOFT_CLIENT_ID 
MICROSOFT_CLIENT_SECRET 
MICROSOFT_TENANT_ID= 
MICROSOFT_CLIENT_STATE 



Google OAuth config

1) create a new project in google cloud console
https://console.cloud.google.com/projectcreate

2) Add all required scopes you can find them in /backend/aomail/constants.py
Link for OAuth consent screen:
https://console.cloud.google.com/projectselector2/auth/overview

Authorized JavaScript origins:
http://localhost

Authorized redirect URIs
http://localhost/signup-link
http://localhost/settings

3) Create a pubsub topic in google cloud console



## Start the application
update the variables in the start.sh 
update the NODE_ENV variable to "development" or "production"
```bash
chmod +x start.sh
```

```bash
./start.sh
```

go to http://localhost:8090/







# Debugging database migrations errors
```bash
sudo rm -fr backend/aomail/migrations
docker exec -it aomail_project-backend_dev-1 python manage.py makemigrations --empty aomail
./start.sh
```

> Aomail does not start - port already used
Make sure the ports are not used by other docker containers
if you have tried to deploy to production, make sur to shutdown the dev containers or change the porduciton ports


# Adding a New Subdomain
1) Add the subdomain in the DNS server.
2) Add the subdomain to your reverse proxy server.
3) Open the required port: `sudo ufw allow PORT_NUMBER` 
4) Update vue.config.js: Add the new domain to the list of allowedHosts.


# check this repo if you want to give yourself unlimited access to Aomail
https://github.com/aomail-ai/aomail-admin-dashboard


# Feature Requests
Open an issue in the repo


# Contributing

(recommended) create a virtual environment and install the dependencies
```bash
python3 -m venv py_env
source py_env/bin/activate
pip install -r requirements.txt
```

Fork the repo and create a new branch for your changes.
Create a pull request to the main branch.
