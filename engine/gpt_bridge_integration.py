"""
gpt_bridge_integration.py — ChatGPT Integration Examples for bridge_main.py
──────────────────────────────────────────────────────────────────────────────

Examples showing how to integrate ChatGPT analysis into the main trading loop.
This file serves as a reference — copy snippets into bridge_main.py as needed.

KEY PATTERNS:
1. Initialize GPT modules at startup
2. Call GPT functions sparingly (they cost tokens!)
3. Cache results to avoid duplicate API calls
4. Log all GPT decisions for audit trail
"""

import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger("bridge_gpt")

# ────────────────────────────────────────────────────────────────
# PATTERN 1: Initialize GPT modules at startup (do this once)
# ────────────────────────────────────────────────────────────────

def initialize_gpt_modules():
    """
    Call this once at bridge_main startup.
    
    Example:
        from gpt_integration import GPTAnalyzer
        from gpt_news_analyzer import NewsAnalyzer
        
        gpt = GPTAnalyzer()
        news_analyzer = NewsAnalyzer(gpt)
        
        print(f"✓ GPT ready (model: {gpt.model})")
        print(f"✓ News analyzer ready (found {len(news_analyzer.get_recent_news())} items)")
    """
    from config import CFG
    from gpt_integration import get_gpt_analyzer
    from gpt_news_analyzer import NewsAnalyzer
    
    if not CFG.gpt.enabled:
        logger.info("GPT disabled in config")
        return None, None
    
    try:
        gpt = get_gpt_analyzer(
            api_key=CFG.gpt.api_key or None,
            model=CFG.gpt.model
        )
        
        if not gpt:
            logger.warning("Failed to initialize GPT")
            return None, None
        
        news_analyzer = NewsAnalyzer(gpt)
        logger.info(f"✓ GPT Integration initialized (model: {gpt.model})")
        
        return gpt, news_analyzer
    
    except Exception as e:
        logger.error(f"GPT initialization failed: {e}")
        return None, None


# ────────────────────────────────────────────────────────────────
# PATTERN 2: Filter signals using news sentiment
# ────────────────────────────────────────────────────────────────

def should_take_signal(
    signal: str,
    win_prob: float,
    news_analyzer,
    gpt_analyzer,
    config
) -> Tuple[bool, str]:
    """
    Enhanced signal filtering with GPT.
    
    Returns:
        (should_trade, reason)
    
    Example in bridge_main.py:
        signal = "BUY"
        should_trade, reason = should_take_signal(signal, 0.72, news_analyzer, gpt, CFG)
        if not should_trade:
            log.info(f"Skipped signal: {reason}")
            continue
    """
    reason = "OK"
    
    # 1. Check news sentiment (if enabled)
    if config.gpt.enable_news_analysis and news_analyzer:
        try:
            if not news_analyzer.filter_trades_by_news(signal, hours=6):
                reason = "News contradicts signal"
                logger.warning(f"Signal {signal} blocked: {reason}")
                return False, reason
        except Exception as e:
            logger.error(f"News filter error: {e}")
    
    # 2. Validate signal with GPT (if enabled)
    if config.gpt.enable_signal_validation and gpt_analyzer:
        try:
            validation = gpt_analyzer.validate_signal(
                signal=signal,
                win_probability=win_prob,
                market_context="Trend following ratchet strategy"
            )
            
            if validation.get("override_recommendation") == "OVERRIDE":
                reason = f"GPT override: {validation.get('reasoning', 'unknown')}"
                logger.warning(f"Signal {signal} overridden: {reason}")
                return False, reason
        
        except Exception as e:
            logger.error(f"Signal validation error: {e}")
    
    return True, reason


# ────────────────────────────────────────────────────────────────
# PATTERN 3: Add trade commentary to dashboard
# ────────────────────────────────────────────────────────────────

def get_trade_commentary(
    price: float,
    signal: str,
    win_prob: float,
    gpt_analyzer,
    config
) -> Optional[dict]:
    """
    Generate GPT commentary for the dashboard.
    
    Returns dict with keys: setup_quality, commentary, risk_level, etc.
    
    Example in bridge_main.py (in the main loop):
        if config.gpt.enable_trade_commentary and new_signal:
            commentary = get_trade_commentary(
                price=current_price,
                signal=signal_value,
                win_prob=win_probability,
                gpt_analyzer=gpt,
                config=config
            )
            if commentary:
                dashboard_data['gpt_commentary'] = commentary
    """
    if not config.gpt.enable_trade_commentary or not gpt_analyzer:
        return None
    
    try:
        commentary = gpt_analyzer.analyze_trade(
            price=price,
            signal=signal,
            win_probability=win_prob,
            market_regime="Trending"  # Pass actual regime from your code
        )
        return commentary
    except Exception as e:
        logger.error(f"Trade commentary error: {e}")
        return None


# ────────────────────────────────────────────────────────────────
# PATTERN 4: Dashboard insights
# ────────────────────────────────────────────────────────────────

def get_dashboard_insights(
    current_price: float,
    open_trades: int,
    daily_pnl: float,
    gpt_analyzer,
    config
) -> Optional[dict]:
    """
    Generate brief market insights for the dashboard.
    
    Returns dict with: market_summary, performance_note, action_prompt
    
    Example in bridge_main.py (update dashboard every N seconds):
        if config.gpt.enable_dashboard_insight:
            insights = get_dashboard_insights(
                current_price=price,
                open_trades=num_open,
                daily_pnl=today_pnl,
                gpt_analyzer=gpt,
                config=config
            )
            if insights:
                dashboard_data['gpt_insight'] = insights
    """
    if not config.gpt.enable_dashboard_insight or not gpt_analyzer:
        return None
    
    try:
        insights = gpt_analyzer.generate_dashboard_insight(
            current_price=current_price,
            price_change_1h=0.5,  # Get from your data
            price_change_24h=2.1,  # Get from your data
            open_trades=open_trades,
            daily_pnl=daily_pnl,
            regime="Trending"  # Get from your code
        )
        return insights
    except Exception as e:
        logger.error(f"Dashboard insight error: {e}")
        return None


# ────────────────────────────────────────────────────────────────
# PATTERN 5: Generate trading reports
# ────────────────────────────────────────────────────────────────

def generate_daily_report(
    trades_today: list,
    gpt_analyzer,
    config
) -> Optional[str]:
    """
    Generate daily AI-powered trade report.
    
    Args:
        trades_today: List of trade dicts from the day
        gpt_analyzer: GPT analyzer instance
        config: Config object
    
    Returns:
        Markdown report string
    
    Example (call this daily after market close):
        if config.gpt.enable_trade_reporting:
            report = generate_daily_report(
                trades_today=today_trades,
                gpt_analyzer=gpt,
                config=config
            )
            if report:
                report_path = f"logs/report_{datetime.now().date()}.md"
                Path(report_path).write_text(report)
                logger.info(f"Report saved: {report_path}")
    """
    if not config.gpt.enable_trade_reporting or not gpt_analyzer:
        return None
    
    if not trades_today:
        return "No trades today."
    
    try:
        report = gpt_analyzer.generate_trade_report(
            trades=trades_today,
            date_range_start=str(datetime.now().date()),
            date_range_end=str(datetime.now().date()),
            include_recommendations=True
        )
        return report
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        return None


# ────────────────────────────────────────────────────────────────
# PATTERN 6: Backtest analysis
# ────────────────────────────────────────────────────────────────

def analyze_recent_backtest(backtest_file: str, gpt_analyzer) -> Optional[str]:
    """
    Analyze backtest results with GPT.
    
    Example (call after running a backtest):
        from gpt_backtest_analyzer import BacktestAnalyzer
        
        bt_analyzer = BacktestAnalyzer(gpt_analyzer=gpt)
        report = analyze_recent_backtest(
            backtest_file="backtest/results/final_backtest.txt",
            gpt_analyzer=gpt
        )
        if report:
            Path("backtest_analysis.md").write_text(report)
    """
    if not gpt_analyzer:
        return None
    
    try:
        from gpt_backtest_analyzer import BacktestAnalyzer
        
        bt_analyzer = BacktestAnalyzer(gpt_analyzer=gpt_analyzer)
        results = bt_analyzer.load_backtest_results(backtest_file)
        
        if not results:
            logger.warning(f"No backtest results found: {backtest_file}")
            return None
        
        report = bt_analyzer.generate_backtest_report(results)
        return report
    
    except Exception as e:
        logger.error(f"Backtest analysis error: {e}")
        return None


# ────────────────────────────────────────────────────────────────
# PATTERN 7: Cost management
# ────────────────────────────────────────────────────────────────

class GPTCostTracker:
    """
    Track GPT costs and enforce daily limits.
    
    Example usage:
        tracker = GPTCostTracker(max_requests_per_day=500)
        
        if not tracker.can_make_request():
            logger.warning(f"Daily GPT limit reached: {tracker.get_stats()}")
            skip_gpt_analysis()
        else:
            result = gpt.analyze_news(...)
            tracker.log_request()
    """
    
    def __init__(self, max_requests_per_day: int = 500):
        self.max_requests = max_requests_per_day
        self.requests_today = 0
        self.last_reset = datetime.now()
    
    def can_make_request(self) -> bool:
        """Check if we can make another API request today."""
        # Reset counter if it's a new day
        if datetime.now().date() > self.last_reset.date():
            self.requests_today = 0
            self.last_reset = datetime.now()
        
        return self.requests_today < self.max_requests
    
    def log_request(self):
        """Log a request."""
        self.requests_today += 1
    
    def get_stats(self) -> dict:
        """Get usage statistics."""
        return {
            "requests_today": self.requests_today,
            "max_requests": self.max_requests,
            "remaining": self.max_requests - self.requests_today,
            "reset_at": (self.last_reset + timedelta(days=1)).strftime("%H:%M:%S")
        }


# ────────────────────────────────────────────────────────────────
# COMPLETE EXAMPLE: Integrate into bridge_main.py
# ────────────────────────────────────────────────────────────────

"""
HOW TO INTEGRATE INTO bridge_main.py:

1. At the top of bridge_main.py, add:
    from gpt_bridge_integration import (
        initialize_gpt_modules,
        should_take_signal,
        get_trade_commentary,
        GPTCostTracker
    )

2. In the main() function, after bridge initialization:
    gpt, news_analyzer = initialize_gpt_modules()
    gpt_cost_tracker = GPTCostTracker(max_requests_per_day=500)

3. In the signal processing loop (when new signal arrives):
    if signal in ["BUY", "SELL"]:
        # Check if we should take it
        should_trade, reason = should_take_signal(
            signal=signal,
            win_prob=win_probability,
            news_analyzer=news_analyzer,
            gpt_analyzer=gpt,
            config=CFG
        )
        
        if not should_trade:
            log.info(f"Skipped: {reason}")
            continue
        
        # Get commentary for dashboard
        if gpt_cost_tracker.can_make_request():
            commentary = get_trade_commentary(
                price=current_price,
                signal=signal,
                win_prob=win_probability,
                gpt_analyzer=gpt,
                config=CFG
            )
            gpt_cost_tracker.log_request()
            if commentary:
                dashboard['gpt_commentary'] = commentary

4. When writing the dashboard (every second):
    # Add GPT insights
    if gpt_cost_tracker.can_make_request():
        insights = get_dashboard_insights(...)
        gpt_cost_tracker.log_request()
    
5. After market close (daily):
    # Generate report
    report = generate_daily_report(today_trades, gpt, CFG)
    if report:
        Path(f"logs/daily_report_{datetime.now().date()}.md").write_text(report)

That's it! The GPT analysis is now integrated into your trading loop.
"""


if __name__ == "__main__":
    print("ChatGPT Bridge Integration Examples")
    print("=" * 50)
    print("\nSee docstrings above for usage patterns.")
    print("\nKey functions:")
    print("  1. initialize_gpt_modules() — Start GPT at bridge startup")
    print("  2. should_take_signal() — Filter signals by news/validation")
    print("  3. get_trade_commentary() — Add commentary to dashboard")
    print("  4. generate_daily_report() — Create AI reports")
    print("  5. analyze_recent_backtest() — Analyze backtest results")
    print("\nSee the COMPLETE EXAMPLE section for bridge_main.py integration.")
