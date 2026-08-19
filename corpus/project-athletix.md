---
title: Project — AthletiX Hub (Conversational E-Commerce)
type: project
url: https://github.com/ANSH1370/AthletiX-Hub
updated: 2026-08-18
---

## What AthletiX Hub is

AthletiX Hub is a full-stack fitness-supplement e-commerce store Ansh built with conversational AI in the purchase flow. Instead of the usual search → cart → checkout steps, customers talk to "Fit Boss," a Dialogflow-powered chatbot that takes orders in natural language.

## The problem it solves

Standard e-commerce forces sequential steps. AthletiX demonstrates conversational commerce: a customer can say "I want 2 whey protein and 1 creatine," adjust the order ("remove the creatine"), and complete it — the AI handles the workflow.

## How AthletiX works

Three tiers: an HTML/CSS/JS frontend with the chatbot embedded, a Flask webhook that receives Dialogflow intents and manages per-session order state, and a MySQL data layer persisting completed orders with status tracking. The bot supports adding/removing items with running totals, order completion with generated order IDs, and order-status tracking by ID.

## Stack

Python, Flask, Dialogflow, MySQL, PyMySQL, Jinja, HTML/CSS/JavaScript.

## Honest limitations

As a prototype, database credentials were hardcoded and authentication is basic — Ansh documents that these need environment variables, parameterized queries, and password hashing for production. Roadmap: payment gateway, inventory management, admin dashboard, and cloud deployment.

## Why this project matters

It's proof Ansh was shipping AI inside real products — chatbot, backend, and database working together — before doing it professionally at Commercient.
