---
title: Project — JobFit ATS Resume Parser
type: project
url: https://github.com/ANSH1370/JobFit_ATS_Resume_Parser
updated: 2026-08-18
---

## What JobFit is

JobFit is an ATS-style resume analysis tool Ansh built. Applicants upload a resume (PDF) and paste a target job description; the system returns AI-powered feedback on how well the resume matches the role.

## The problem it solves

Job seekers usually get rejected without any constructive feedback. JobFit bridges that gap with a detailed analysis of the resume against a specific job posting — the same kind of screening recruiters' ATS software performs.

## How JobFit works

The resume PDF is converted for analysis (pdf2image + PIL), then Google's Gemini model analyzes the resume together with the job description. Feedback comes across four dimensions: general resume quality, skill-gap identification with recommendations, missing keyword detection, and a match percentage score indicating resume-to-job alignment.

## Stack

Python, Streamlit, Google Generative AI (Gemini), pdf2image, PIL.

## Honest limitations

Currently supports single-page resumes. Planned improvements include multi-page handling, customizable feedback categories, inline resume editing, and better error handling for varied file formats.
