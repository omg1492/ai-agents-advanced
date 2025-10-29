# Lesson 00 - Preparation
Following topics are technical concepts you should now before starting the lessons as well as requirements for your setup and access to services.

## Access to services
- **Make sure you have access to `OpenAI` or `Azure OpenAI`** API keys with enough credit (I will be using Azure OpenAI for which you can get Azure trail subscription for free, but going directly with OpenAI is also fine, althow not fully tested in my code)
- Recommendation is to go with [Azure Trial](https://azure.microsoft.com/en-us/pricing/purchase-options/azure-account) or with your company Azure. Alternatively use [OpenAI Platform](https://platform.openai.com/settings/organization/billing/overview) and add some credit (absolute majority of our example code is using latest OpenAI SDK which works the same between Azure and OpenA flavors using **Responses API** so it should work fine)
- You will need AI code assistant, I will be using (and recommend) **GitHub Copilot** - you need at least Pro version (or Pro+, Bussines or Enterprise) which youc by for 10 USD or get trial [here](https://github.com/features/copilot/plans)

## Concepts recommended to know before starting this course
- Learn `uv` - a Python environment and package manager
- You should know basics of `Docker` (creating Dockerfiles, building images, running containers) and `Docker Compose` (YAML file syntax,docker compose up, down, logs, etc.)
- Get familiar with Python concepts and libraries like `classes`, `Pydantic`, `FastAPI`, `SQLAlchemy`, `pytest`, and `Jinja2`
- Basic understanding of how to run `React` apps, use `npm`, have it installed on your machine
- Learn basics of `PostgreSQL` (creating databases, tables, running queries), knowing little bit of `pgvector` is a plus
- Get familiar with `GitHub Copilot` (this is what I will be using, but if you are user of Cursor or Windsurf, it is fine too)
- Basics of `git` and `GitHub` (cloning repositories, creating branches, committing changes, pushing to remote)
  
## Requirements for your machine
For local machine make sure you have all required permissions (things like containers, networking, ability to install software, ...) and install the following tools:
- Visual Studio Code and log in with GitHub Copilot
- Have `Python` and `npm` installed on your machine
- Install `Rancher Desktop` in Docker compatibility mode and test it - or alternatively use any other local Linux Docker compatible system

Alternatively you can use **GitHub Codespaces** to get cloud-based dev environment.