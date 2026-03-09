# KHI Segment Classifier

AI-powered tool that classifies esanum KHI (Kongress Highlights) articles by medical specialty using Claude API.

## What it does

1. Reads KHI article data from Excel files (title, teaser, content)
2. Cleans HTML tags from article content
3. Sends all articles to Claude AI for analysis
4. Assigns primary, secondary, and tertiary `segment_id` from the allowed specialties list
5. Outputs classified results as Excel or displays on a web dashboard

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY='your-key-here'
```

## Usage

### CLI

```bash
python classify.py <khi_articles.xlsx> <specialties.xlsx> --output result.xlsx
```

### Web Dashboard

```bash
python app.py --port 5001
```

Open http://localhost:5001 — upload an xlsx file and get results on the dashboard.

### API

```bash
curl -X POST http://localhost:5001/api/classify \
  -F "khi_file=@articles.xlsx" \
  -F "specialties_file=@specialties.xlsx"
```

## Tests

```bash
python -m pytest test_classify.py -v
```

## Input Format

**KHI Articles Excel** — columns: `S no`, `title`, `teaser`, `content`

**Specialties Excel** — columns: `segment_id`, `specialty_id`, `segment_name`, `total reach`

## Output

Excel file with columns: S no, title, teaser, content (cleaned), primary_segment_id, primary_segment_name, primary_reasoning, secondary_segment_id, secondary_segment_name, secondary_reasoning, tertiary_segment_id, tertiary_segment_name, tertiary_reasoning
