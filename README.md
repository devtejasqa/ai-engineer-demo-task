# AI Engineer Demo Task

## Overview
Data ingestion pipeline for startups, products, research papers, jobs, and news
in the AI/VC ecosystem. Built for the GraphOne/FrontierAtlas AI Engineer trial.

## Setup
1. Create a virtual environment: python -m venv venv
2. Activate it: venv\Scripts\activate
3. Install dependencies: pip install -r requirements.txt
4. (Optional) Add API keys to .env for LLM orchestration (Gemini/Groq/DeepSeek)

## Running the pipeline
- python src\main.py          # Scrapes research papers + resolves entities
- python src\startup_scraper.py
- python src\product_scraper.py
- python src\jobs_scraper.py
- python src\news_scraper.py

## Data sources
- Research Papers: paperswithcode.co (JSON-LD extraction) + GitHub API for star counts
- Startups/Products: YC Open Source company dataset
- Jobs: RemoteOK public API
- News: Hacker News public API

## Known limitations
- GitHub API rate limit (60/hr unauthenticated) means some papers show null star counts
- Jobs tab may be empty depending on scrape timing (strict 24hr freshness filter)
- LLM orchestrator (src/llm_orchestrator.py) is built but not wired into main.py -
  requires API keys not available during this trial
- Papers scraped: 200 of 1000 target (time-constrained), architecture supports scaling

## Architecture
See architecture.pdf for full design documentation covering scale strategy,
rate limit handling, freshness tracking, and storage strategy.
