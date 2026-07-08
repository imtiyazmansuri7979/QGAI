# ChatGPT Integration for QGAI — Setup & Usage Guide

## Overview

This integration adds **6 AI-powered features** to your QGAI trading system:

1. **News Analysis** — Interpret economic news to filter/validate trades
2. **Trade Commentary** — Real-time AI analysis of market setups
3. **Signal Validation** — Skeptical review of model signals
4. **Dashboard Insights** — Brief market summaries for the dashboard
5. **Strategy Review** — Backtest analysis with improvement suggestions
6. **Custom Reporting** — AI-generated daily/weekly trade reports

---

## Setup

### 1. Install OpenAI Library

```bash
pip install openai>=1.3.0
```

Or use the updated `requirements.txt`:

```bash
cd QGAI/engine
pip install -r requirements.txt
```

### 2. Get an OpenAI API Key

1. Go to https://platform.openai.com/account/api-keys
2. Create a new API key
3. Copy it somewhere safe

### 3. Set the Environment Variable

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY = "sk-your-key-here"
```

**Windows (Command Prompt):**
```cmd
set OPENAI_API_KEY=sk-your-key-here
```

**Linux/Mac (Bash):**
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

**Persistent (Windows):**
- Settings → System → Environment Variables
- New → Variable name: `OPENAI_API_KEY`
- Variable value: `sk-your-key-here`
- Restart your terminal/IDE

### 4. Configure in QGAI

Edit `engine/config.py` to customize GPT settings:

```python
@dataclass
class GPTConfig:
    enabled = True                           # Enable/disable all GPT
    model = "gpt-4o-mini"                   # Model choice
    enable_news_analysis = True              # Enable news filtering
    enable_trade_commentary = True           # Dashboard commentary
    enable_signal_validation = False         # Disable to save tokens
    enable_dashboard_insight = True          # Market summaries
    enable_backtest_analysis = True          # Backtest reports
    enable_trade_reporting = True            # Daily reports
    max_requests_per_day = 500               # Cost control
```

---

## Quick Start

### Test It Works

```python
# Test 1: Basic news analysis
from gpt_integration import GPTAnalyzer

gpt = GPTAnalyzer()
analysis = gpt.analyze_news("Fed raises interest rates")
print(analysis)

# Test 2: Trade analysis
commentary = gpt.analyze_trade(
    price=2500.50,
    signal="BUY",
    win_probability=0.72
)
print(commentary)

# Test 3: Dashboard insights
insights = gpt.generate_dashboard_insight(
    current_price=2500.50,
    price_change_1h=0.25,
    price_change_24h=1.20,
    open_trades=1,
    daily_pnl=150.00,
    regime="Trending"
)
print(insights)
```

Run the test files directly:

```bash
python engine/gpt_integration.py          # Full GPT test
python engine/gpt_news_analyzer.py        # News analyzer test
python engine/gpt_backtest_analyzer.py    # Backtest analyzer test
```

---

## Usage Patterns

### Pattern 1: Filter Trades by News Sentiment

```python
from gpt_news_analyzer import NewsAnalyzer

analyzer = NewsAnalyzer()

# Get market sentiment from recent news
sentiment = analyzer.get_market_sentiment(hours=6)
print(sentiment)  # "bullish", "bearish", "neutral"

# Filter: don't trade BUY if news is bearish
if not analyzer.filter_trades_by_news(signal="BUY", hours=6):
    print("Skipping BUY due to bearish news")
    continue
```

### Pattern 2: Add Commentary to Dashboard

```python
from gpt_integration import GPTAnalyzer

gpt = GPTAnalyzer()

# Generate setup commentary
commentary = gpt.analyze_trade(
    price=2500.50,
    signal="BUY",
    win_probability=0.72,
    market_regime="Trending",
    atr_pct=0.15,
    volume_spike=True
)

# Add to dashboard JSON
dashboard_data['gpt_commentary'] = commentary['commentary']
dashboard_data['setup_quality'] = commentary['setup_quality']
```

### Pattern 3: Validate Signals

```python
# Let GPT review the model's signal
validation = gpt.validate_signal(
    signal="SELL",
    win_probability=0.65,
    market_context="Gold trending down on USD strength"
)

if validation['override_recommendation'] == "OVERRIDE":
    print(f"⚠️  GPT disagrees: {validation['reasoning']}")
    skip_signal = True
```

### Pattern 4: Generate Daily Reports

```python
trades_today = [
    {"entry_time": "09:30", "exit_time": "10:15", "pnl": 125.50, "reason": "TP hit"},
    {"entry_time": "11:00", "exit_time": "11:45", "pnl": -75.25, "reason": "SL hit"},
]

report = gpt.generate_trade_report(
    trades=trades_today,
    date_range_start="2026-06-25",
    date_range_end="2026-06-25",
    include_recommendations=True
)

print(report)
# Output: Markdown report with analysis, insights, recommendations
```

### Pattern 5: Analyze Backtests

```python
from gpt_backtest_analyzer import BacktestAnalyzer

analyzer = BacktestAnalyzer()

# Load backtest file
results = analyzer.load_backtest_results("backtest/results/final_backtest.txt")

# Analyze with GPT
analysis = analyzer.analyze_results(results)
print(analysis['performance_assessment'])
print(analysis['strengths'])
print(analysis['weaknesses'])

# Get improvement suggestions
suggestions = analyzer.get_improvement_suggestions(results)
for i, suggestion in enumerate(suggestions, 1):
    print(f"{i}. {suggestion}")

# Compare two backtests
baseline = analyzer.load_backtest_results("backtest/baseline.txt")
new = analyzer.load_backtest_results("backtest/new.txt")

comparison = analyzer.compare_backtests(baseline, new)
print(f"Verdict: {comparison['verdict']}")
```

### Pattern 6: Full Integration in bridge_main.py

See `gpt_bridge_integration.py` for complete examples. Quick version:

```python
# 1. At startup
from gpt_bridge_integration import initialize_gpt_modules, should_take_signal

gpt, news_analyzer = initialize_gpt_modules()

# 2. When signal arrives
should_trade, reason = should_take_signal(
    signal=signal,
    win_prob=win_prob,
    news_analyzer=news_analyzer,
    gpt_analyzer=gpt,
    config=CFG
)

if not should_trade:
    log.info(f"Skipped: {reason}")
    continue

# 3. Get dashboard commentary
from gpt_bridge_integration import get_trade_commentary

commentary = get_trade_commentary(
    price=price,
    signal=signal,
    win_prob=win_prob,
    gpt_analyzer=gpt,
    config=CFG
)
if commentary:
    dashboard['gpt_commentary'] = commentary
```

---

## Cost Management

### API Pricing (As of June 2026)

- **gpt-4o-mini**: $0.15/M input tokens, $0.60/M output tokens (cheapest)
- **gpt-3.5-turbo**: $0.50/M input, $1.50/M output
- **gpt-4**: $3/M input, $6/M output (most powerful)

### Estimated Costs

| Feature | Requests/Day | Tokens/Request | Daily Cost |
|---------|--------------|---|---|
| News analysis | 10 | ~300 | $0.05 |
| Trade commentary | 10 | ~250 | $0.04 |
| Dashboard insights | 20 | ~200 | $0.06 |
| Daily report | 1 | ~500 | $0.01 |
| **Total** | **~41** | | **~$0.16** |

### Cost Control

1. **Disable unused features** in `config.py`:
   ```python
   enable_signal_validation = False  # Costs tokens but adds little value
   enable_news_analysis = True       # Cheap, high value
   ```

2. **Limit requests per day**:
   ```python
   max_requests_per_day = 500  # Enforce limit
   ```

3. **Cache responses**:
   ```python
   cache_responses = True  # Avoids duplicate API calls
   ```

4. **Use cheaper models**:
   ```python
   model = "gpt-4o-mini"  # Cheapest, still very capable
   ```

### Monitor Usage

```python
from gpt_integration import GPTAnalyzer

gpt = GPTAnalyzer()

# ... make some API calls ...

stats = gpt.get_stats()
print(f"API requests: {stats['requests']}")
print(f"Est. tokens: {stats['estimated_tokens']}")

# Estimate cost
tokens = stats['estimated_tokens']
input_cost = tokens * 0.15 / 1_000_000  # gpt-4o-mini
print(f"Est. cost: ${input_cost:.4f}")
```

---

## Troubleshooting

### "OPENAI_API_KEY not set"

**Solution:**
```bash
# Check if set correctly
echo $OPENAI_API_KEY  # Linux/Mac
echo %OPENAI_API_KEY%  # Windows CMD
Write-Host $env:OPENAI_API_KEY  # PowerShell

# Set it (temporary, current terminal only)
export OPENAI_API_KEY="sk-your-key"  # Linux/Mac
set OPENAI_API_KEY=sk-your-key       # Windows CMD

# Set it permanently → Windows System Settings
```

### "openai" library not found

**Solution:**
```bash
pip install openai>=1.3.0
# Or reinstall all requirements
pip install -r engine/requirements.txt
```

### API request timeouts

**Solution:**
```python
# Increase timeout in config.py
gpt.timeout_sec = 30.0  # Default is 10

# Or pass when initializing
gpt = GPTAnalyzer()
gpt.timeout_sec = 30.0
```

### Response parsing errors (JSON decode)

**Solution:**
This usually means GPT returned an unexpected format. Check:
- Model availability
- Token limit not exceeded
- API not rate-limited

Try forcing a simpler model:
```python
gpt = GPTAnalyzer(model="gpt-3.5-turbo")
```

### Too many API requests / Rate limit

**Solution:**
```python
# Reduce daily limit in config
max_requests_per_day = 100  # Instead of 500

# Or disable expensive features
enable_signal_validation = False  # High token cost
```

---

## Examples by Feature

### News Analysis Example

```python
from gpt_news_analyzer import NewsAnalyzer

analyzer = NewsAnalyzer()

# Load recent news
news = analyzer.get_recent_news(hours=24, limit=5)

# Analyze each
for item in news:
    headline = item['headline']
    analysis = analyzer.analyze_with_gpt(item, current_price=2500)
    
    print(f"\n{headline}")
    print(f"  Impact: {analysis['impact_on_gold']}")
    print(f"  Trade Action: {analysis['trade_action']}")
    print(f"  Confidence: {analysis['confidence']*100:.0f}%")

# Get overall sentiment
sentiment = analyzer.get_market_sentiment(hours=24)
print(f"\nOverall Market Bias: {sentiment}")
```

### Dashboard Integration Example

```python
# In bridge_main.py, update dashboard JSON

dashboard_data = {
    'price': 2500.50,
    'open_trades': 1,
    'daily_pnl': 150.00,
}

# Add GPT insights
if CFG.gpt.enable_dashboard_insight:
    insights = gpt.generate_dashboard_insight(
        current_price=2500.50,
        price_change_1h=0.25,
        price_change_24h=1.20,
        open_trades=1,
        daily_pnl=150.00,
        regime="Trending",
        win_rate=0.68
    )
    if insights:
        dashboard_data['gpt'] = insights
        # Output in dashboard.html:
        # <div class="gpt-insight">\n
        # <p>{{ insights.market_summary }}</p>\n
        # <p>{{ insights.action_prompt }}</p>\n
        # </div>

write_dashboard(dashboard_data)
```

### Backtest Analysis Example

```python
from gpt_backtest_analyzer import BacktestAnalyzer

analyzer = BacktestAnalyzer()

# Run backtest → save results
# Then analyze:
results = analyzer.load_backtest_results("backtest/results/final_backtest.txt")

# Generate full report
report = analyzer.generate_backtest_report(results)

# Save and share
Path("backtest_analysis_2026-06-25.md").write_text(report)
print("✓ Report saved: backtest_analysis_2026-06-25.md")
```

---

## FAQ

### Q: Will GPT trading make me more money?

**A:** GPT provides insights, not certainty. Use it to:
- Avoid news-driven whipsaws (filter trades)
- Understand what's working/broken in backtests
- Generate professional reports
- Debug strategy issues

It's a tool, not a crystal ball.

### Q: Which model should I use?

**A:** Use **gpt-4o-mini** (default). It's:
- 10x cheaper than gpt-4
- Just as accurate for this use case
- Fastest response time

### Q: Can I use GPT for live signal generation?

**A:** Not recommended. GPT is:
- Too slow (1-2 sec latency)
- Too expensive
- Designed for analysis, not high-frequency trading

Use it for:
- Signal validation (confirm/reject after generation)
- Commentary (explain trades after the fact)
- Analysis (weekly reviews)

### Q: What if my API quota runs out?

**A:** 
1. Check your usage at https://platform.openai.com/account/usage
2. Set spending limit in account settings
3. Reduce max_requests_per_day in config
4. Disable expensive features

### Q: Can I use local GPT / offline models?

**A:** Yes, but requires more setup. You'd need:
- Local LLM (Ollama, LM Studio, etc.)
- Modify GPT calls to use local API
- Trade quality for cost (local models are less capable)

For now, stick with OpenAI API.

---

## Next Steps

1. ✅ Install openai library
2. ✅ Set OPENAI_API_KEY environment variable
3. ✅ Test with `python engine/gpt_integration.py`
4. ✅ Enable features in `config.py`
5. ✅ Integrate into `bridge_main.py` (see `gpt_bridge_integration.py`)
6. ✅ Monitor costs daily
7. ✅ Refine prompts based on results

---

## Support & Debugging

If something breaks:

1. Check logs: `logs/qgai.log` and `logs/live_trades.csv`
2. Run test scripts to isolate the issue
3. Review your API key and permissions
4. Check rate limits / quota

**Debug mode:**

```python
from config import CFG

CFG.gpt.log_all_requests = True  # Log every request/response
logger.setLevel(logging.DEBUG)   # Verbose logging
```

This will show all GPT requests and responses in the console.

---

**Created:** 2026-06-25  
**Last Updated:** 2026-06-25  
**Status:** Complete ✓
