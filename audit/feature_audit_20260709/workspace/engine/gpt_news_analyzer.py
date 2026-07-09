"""
gpt_news_analyzer.py — Economic News Analysis with ChatGPT
──────────────────────────────────────────────────────────────

Pulls economic news (from CSV) and uses GPT to assess impact on XAUUSD trading.
Integrates with the bridge to filter/validate trade signals.

Usage:
    from gpt_news_analyzer import NewsAnalyzer
    
    analyzer = NewsAnalyzer()
    
    # Get current/recent news
    news_items = analyzer.get_recent_news(hours=6)
    
    # Analyze each item
    for news in news_items:
        gpt_analysis = analyzer.analyze_with_gpt(news)
        print(f"{news['headline']}: {gpt_analysis['trade_action']}")
    
    # Get overall market sentiment
    sentiment = analyzer.get_market_sentiment()
    print(f"Market Bias: {sentiment}")  # "bullish", "bearish", or "neutral"
"""

import pandas as pd
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from config import CFG
from gpt_integration import GPTAnalyzer, get_gpt_analyzer

logger = logging.getLogger("news_analyzer")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class NewsAnalyzer:
    """Analyze economic news and its impact on gold trading."""

    def __init__(self, gpt_analyzer: Optional[GPTAnalyzer] = None):
        """
        Initialize the news analyzer.
        
        Args:
            gpt_analyzer: Optional GPTAnalyzer instance. If None, will create one.
        """
        self.gpt = gpt_analyzer or get_gpt_analyzer()
        if not self.gpt:
            logger.warning("GPT not available — news analysis will be limited")
        
        self.news_file = Path(CFG.paths.news_file)
        self.cache = {}  # Simple cache: headline → gpt_analysis
        logger.info(f"News analyzer initialized (file: {self.news_file.name})")

    def get_recent_news(
        self,
        hours: int = 24,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Load recent news from CSV file.
        
        Args:
            hours: Only include news from last N hours
            limit: Max number of items to return
        
        Returns:
            List of dicts: {date, headline, impact, surprise, etc.}
        """
        if not self.news_file.exists():
            logger.warning(f"News file not found: {self.news_file}")
            return []
        
        try:
            df = pd.read_csv(self.news_file)
            if df.empty:
                return []
            
            # Parse date column (adjust if your CSV has different column name)
            date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()]
            if not date_cols:
                logger.warning("No date column found in news CSV")
                return df.to_dict('records')[:limit] if limit else df.to_dict('records')
            
            date_col = date_cols[0]
            try:
                df[date_col] = pd.to_datetime(df[date_col])
                cutoff = datetime.now() - timedelta(hours=hours)
                df = df[df[date_col] >= cutoff]
            except:
                logger.warning(f"Could not parse dates from {date_col}")
            
            df = df.sort_values(date_col, ascending=False)
            result = df.to_dict('records')
            
            if limit:
                result = result[:limit]
            
            logger.info(f"Loaded {len(result)} news items from last {hours} hours")
            return result
        
        except Exception as e:
            logger.error(f"Failed to load news: {e}")
            return []

    def analyze_with_gpt(
        self,
        news_item: Dict[str, Any],
        current_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Use ChatGPT to analyze a single news item.
        
        Args:
            news_item: Dict with at least 'headline' key
            current_price: Optional current gold price
        
        Returns:
            GPT analysis dict
        """
        if not self.gpt:
            return {
                "sentiment": "neutral",
                "impact_on_gold": "neutral",
                "intensity": 0,
                "reasoning": "GPT not available",
                "trade_action": "NEUTRAL",
                "confidence": 0.0
            }
        
        headline = news_item.get("headline", "")
        if not headline:
            return {"sentiment": "neutral", "impact_on_gold": "neutral"}
        
        # Check cache
        if headline in self.cache:
            return self.cache[headline]
        
        # Extract optional context from the news item
        context = news_item.get("impact", "")
        
        try:
            result = self.gpt.analyze_news(
                news_headline=headline,
                news_context=context,
                current_price=current_price
            )
            self.cache[headline] = result
            return result
        except Exception as e:
            logger.error(f"GPT analysis failed for: {headline[:50]}... — {e}")
            return {
                "sentiment": "neutral",
                "impact_on_gold": "neutral",
                "intensity": 0,
                "reasoning": str(e),
                "trade_action": "NEUTRAL",
                "confidence": 0.0
            }

    def get_market_sentiment(self, hours: int = 24) -> str:
        """
        Analyze recent news to determine overall market bias.
        
        Args:
            hours: Consider news from last N hours
        
        Returns:
            "bullish", "bearish", or "neutral"
        """
        news_items = self.get_recent_news(hours=hours, limit=10)
        if not news_items:
            return "neutral"
        
        bullish_count = 0
        bearish_count = 0
        
        for item in news_items:
            analysis = self.analyze_with_gpt(item)
            impact = analysis.get("impact_on_gold", "neutral")
            confidence = analysis.get("confidence", 0.0)
            
            if impact == "positive" and confidence > 0.5:
                bullish_count += 1
            elif impact == "negative" and confidence > 0.5:
                bearish_count += 1
        
        if bullish_count > bearish_count:
            return "bullish"
        elif bearish_count > bullish_count:
            return "bearish"
        else:
            return "neutral"

    def filter_trades_by_news(
        self,
        signal: str,  # "BUY" or "SELL"
        hours: int = 6
    ) -> bool:
        """
        Should we take this trade given recent news sentiment?
        
        Args:
            signal: Model signal (BUY or SELL)
            hours: Consider news from last N hours
        
        Returns:
            True if news doesn't contradict the signal, False if it does
        """
        sentiment = self.get_market_sentiment(hours=hours)
        
        # If no strong sentiment, allow the trade
        if sentiment == "neutral":
            return True
        
        # Check for counter-trend signals
        if signal == "BUY" and sentiment == "bearish":
            logger.warning(f"News is bearish but model says BUY — high risk")
            return False
        
        if signal == "SELL" and sentiment == "bullish":
            logger.warning(f"News is bullish but model says SELL — high risk")
            return False
        
        return True

    def generate_news_report(self, hours: int = 24) -> str:
        """Generate a summary of recent economic news for reports."""
        news_items = self.get_recent_news(hours=hours, limit=5)
        
        if not news_items:
            return "No recent news available."
        
        report = f"\n### Economic News (Last {hours}h)\n\n"
        for item in news_items:
            headline = item.get("headline", "Unknown")
            analysis = self.analyze_with_gpt(item)
            report += f"- **{headline}**\n"
            report += f"  Impact: {analysis.get('impact_on_gold', 'N/A').capitalize()}\n"
            report += f"  Confidence: {analysis.get('confidence', 0)*100:.0f}%\n\n"
        
        return report


# ────────────────────────────────────────────────────────────────
# Integration helpers for bridge_main.py
# ────────────────────────────────────────────────────────────────

def should_skip_trade_due_to_news(signal: str, news_analyzer: NewsAnalyzer) -> bool:
    """
    Quick check: should we skip this signal due to news?
    
    Usage in bridge_main.py:
        from gpt_news_analyzer import should_skip_trade_due_to_news
        
        if should_skip_trade_due_to_news(signal, news_analyzer):
            log.info("Skipping trade due to conflicting news")
            continue
    """
    if not news_analyzer:
        return False
    
    try:
        return not news_analyzer.filter_trades_by_news(signal, hours=6)
    except Exception as e:
        logger.error(f"News filter failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing News Analyzer...")
    
    try:
        analyzer = NewsAnalyzer()
        
        # Test 1: Load recent news
        news = analyzer.get_recent_news(hours=168, limit=3)
        print(f"\n1. Recent News: Found {len(news)} items")
        for n in news[:2]:
            print(f"   - {n.get('headline', 'N/A')[:60]}")
        
        # Test 2: Analyze with GPT
        if news:
            print(f"\n2. Analyzing first news item...")
            analysis = analyzer.analyze_with_gpt(news[0])
            print(f"   Impact: {analysis.get('impact_on_gold', 'N/A')}")
            print(f"   Confidence: {analysis.get('confidence', 0)*100:.0f}%")
        
        # Test 3: Get market sentiment
        print(f"\n3. Market Sentiment: {analyzer.get_market_sentiment(hours=72)}")
        
        print("\n✓ News analyzer working!")
    
    except Exception as e:
        print(f"✗ Test failed: {e}")
