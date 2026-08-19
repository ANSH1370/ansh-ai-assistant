---
title: Project — ContextFlow (LSTM Next-Word Prediction)
type: project
url: https://github.com/ANSH1370/ContextFlow-LSTM-Language-Model-for-Next-Word-Prediction
updated: 2026-08-18
---

## What ContextFlow is

ContextFlow is an LSTM-based language model Ansh built from scratch for next-word prediction — the foundation behind autocomplete, smart keyboards, and suggestion systems. It trains on text from the "Attention Is All You Need" paper and learns vocabulary patterns and contextual word relationships.

## How ContextFlow works

Pipeline: extract and clean raw PDF text → tokenize into words → build numerical vocabulary mappings → generate input/output sequence pairs → train the LSTM → predict by generating a probability distribution over the vocabulary and taking the highest-probability word. The network stacks embedding layers, recurrent LSTM units that maintain temporal memory, and dense output layers.

## Stack

Python, TensorFlow 2.x, Keras, NumPy, Pandas, Jupyter.

## Results and honest limitations

The model reaches roughly 98% next-word accuracy on its training corpus — but that number mostly reflects the small single-corpus vocabulary rather than general performance, and Ansh documents that openly. Extensions on the roadmap: perplexity metrics, temperature-based sampling, LSTM vs GRU vs n-gram comparisons, and a web interface.
