---
title: Project — SmartPhone Price Intelligence (SmartPrice AI)
type: project
url: https://github.com/ANSH1370/SmartPhone-Price-Intelligence
updated: 2026-08-18
---

## What SmartPhone Price Intelligence is

SmartPrice AI is a machine-learning platform Ansh built that predicts smartphone selling prices from hardware specifications. It demonstrates a complete data-science workflow — from web scraping its own training data through model deployment in an interactive app.

## The problem it solves

Estimating a phone's market price requires understanding complex relationships between many device attributes (processor, memory, camera, battery, brand) and market value. The project automates that estimation.

## How it works

Pipeline: Selenium-based scraper collects listings from Smartprix → multi-stage cleaning (raw → EDA → cleaned → final datasets) → feature engineering across 20+ smartphone attributes → two regression models trained for comparison (Linear Regression baseline and Random Forest) → interactive Streamlit app where users configure a hypothetical phone (brand, 5G, processor, RAM/ROM, battery, display, camera, OS, fast charging) and get predicted prices from both models side by side.

## Stack

Python, Selenium, Pandas, NumPy, scikit-learn (OneHotEncoder, ColumnTransformer, Pipeline), Linear Regression, Random Forest, Streamlit. Evaluation with MAE, MSE, RMSE, median absolute error, and R².

## Results and honest limitations

Random Forest showed better accuracy than the linear baseline on the collected dataset, though results vary with dataset version and preprocessing choices. Known constraints: static training without automated retraining, no hyperparameter optimization yet, and dataset refresh requires manual scraping. The roadmap includes XGBoost, SHAP explainability, and API/Docker deployment.
